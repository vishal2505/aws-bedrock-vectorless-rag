# ===========================================================================
# Data sources
# ===========================================================================

data "aws_caller_identity" "current" {}

locals {
  # Bucket names must be globally unique — append account ID as a suffix.
  documents_bucket_name = "${var.project_name}-docs-${data.aws_caller_identity.current.account_id}"
  dynamodb_table_name   = "${var.project_name}-rag-index"
}

# ===========================================================================
# S3 — Document storage
# ===========================================================================

resource "aws_s3_bucket" "documents" {
  bucket = local.documents_bucket_name
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket                  = aws_s3_bucket.documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ===========================================================================
# DynamoDB — Tree index & node text storage
#
# Schema:
#   PK: doc_id        (String)
#   SK: record_type   (String)
#
#   record_type = "tree_metadata"  → item.tree  (JSON string, no text)
#   record_type = "node#<node_id>" → item.text  (full leaf node text)
# ===========================================================================

resource "aws_dynamodb_table" "rag_index" {
  name         = local.dynamodb_table_name
  billing_mode = "PAY_PER_REQUEST"   # no capacity planning needed for variable workloads
  hash_key     = "doc_id"
  range_key    = "record_type"

  attribute {
    name = "doc_id"
    type = "S"
  }

  attribute {
    name = "record_type"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }
}

# ===========================================================================
# Lambda packaging
#
# deploy.sh creates lambda_package/ by installing requirements and copying
# source files.  Terraform then zips that directory and hashes it so that
# any code change triggers a Lambda update.
# ===========================================================================

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda_package"
  output_path = "${path.module}/../lambda_package.zip"
}

# ===========================================================================
# Lambda — Ingest
# ===========================================================================

resource "aws_lambda_function" "ingest" {
  function_name    = "${var.project_name}-ingest"
  role             = aws_iam_role.lambda_exec.arn
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  handler          = "ingest_handler.handler"
  runtime          = "python3.11"
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory_size

  environment {
    variables = {
      DOCUMENTS_BUCKET = aws_s3_bucket.documents.bucket
      DYNAMODB_TABLE   = aws_dynamodb_table.rag_index.name
      BEDROCK_MODEL_ID = var.bedrock_model_id
      LOG_LEVEL        = "INFO"
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.ingest_logs,
    aws_iam_role_policy_attachment.lambda_basic,
  ]
}

resource "aws_cloudwatch_log_group" "ingest_logs" {
  name              = "/aws/lambda/${var.project_name}-ingest"
  retention_in_days = var.log_retention_days
}

# ===========================================================================
# Lambda — Query
# ===========================================================================

resource "aws_lambda_function" "query" {
  function_name    = "${var.project_name}-query"
  role             = aws_iam_role.lambda_exec.arn
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  handler          = "query_handler.handler"
  runtime          = "python3.11"
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory_size

  environment {
    variables = {
      DOCUMENTS_BUCKET    = aws_s3_bucket.documents.bucket
      DYNAMODB_TABLE      = aws_dynamodb_table.rag_index.name
      BEDROCK_MODEL_ID    = var.bedrock_model_id
      MAX_RETRIEVED_NODES = tostring(var.max_retrieved_nodes)
      LOG_LEVEL           = "INFO"
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.query_logs,
    aws_iam_role_policy_attachment.lambda_basic,
  ]
}

resource "aws_cloudwatch_log_group" "query_logs" {
  name              = "/aws/lambda/${var.project_name}-query"
  retention_in_days = var.log_retention_days
}

# ===========================================================================
# API Gateway REST API
# ===========================================================================

resource "aws_api_gateway_rest_api" "rag_api" {
  name        = "${var.project_name}-api"
  description = "Vectorless RAG API — ingest and query endpoints"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

# ---------------------------------------------------------------------------
# /ingest  (POST)
# ---------------------------------------------------------------------------

resource "aws_api_gateway_resource" "ingest" {
  rest_api_id = aws_api_gateway_rest_api.rag_api.id
  parent_id   = aws_api_gateway_rest_api.rag_api.root_resource_id
  path_part   = "ingest"
}

resource "aws_api_gateway_method" "ingest_post" {
  rest_api_id   = aws_api_gateway_rest_api.rag_api.id
  resource_id   = aws_api_gateway_resource.ingest.id
  http_method   = "POST"
  authorization = "NONE"
  # To add API key auth later, set:
  #   authorization  = "NONE"
  #   api_key_required = true
}

resource "aws_api_gateway_integration" "ingest_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.rag_api.id
  resource_id             = aws_api_gateway_resource.ingest.id
  http_method             = aws_api_gateway_method.ingest_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.ingest.invoke_arn
}

# ---------------------------------------------------------------------------
# /query  (POST)
# ---------------------------------------------------------------------------

resource "aws_api_gateway_resource" "query" {
  rest_api_id = aws_api_gateway_rest_api.rag_api.id
  parent_id   = aws_api_gateway_rest_api.rag_api.root_resource_id
  path_part   = "query"
}

resource "aws_api_gateway_method" "query_post" {
  rest_api_id   = aws_api_gateway_rest_api.rag_api.id
  resource_id   = aws_api_gateway_resource.query.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "query_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.rag_api.id
  resource_id             = aws_api_gateway_resource.query.id
  http_method             = aws_api_gateway_method.query_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.query.invoke_arn
}

# ---------------------------------------------------------------------------
# /presign  (POST) — generates presigned S3 PUT URLs for browser uploads
# ---------------------------------------------------------------------------

resource "aws_lambda_function" "presign" {
  function_name    = "${var.project_name}-presign"
  role             = aws_iam_role.lambda_exec.arn
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  handler          = "presign_handler.handler"
  runtime          = "python3.11"
  timeout          = 30
  memory_size      = 256

  environment {
    variables = {
      DOCUMENTS_BUCKET       = aws_s3_bucket.documents.bucket
      PRESIGN_EXPIRY_SECONDS = "300"
      LOG_LEVEL              = "INFO"
    }
  }

  depends_on = [aws_cloudwatch_log_group.presign_logs]
}

resource "aws_cloudwatch_log_group" "presign_logs" {
  name              = "/aws/lambda/${var.project_name}-presign"
  retention_in_days = var.log_retention_days
}

resource "aws_api_gateway_resource" "presign" {
  rest_api_id = aws_api_gateway_rest_api.rag_api.id
  parent_id   = aws_api_gateway_rest_api.rag_api.root_resource_id
  path_part   = "presign"
}

resource "aws_api_gateway_method" "presign_post" {
  rest_api_id   = aws_api_gateway_rest_api.rag_api.id
  resource_id   = aws_api_gateway_resource.presign.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "presign_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.rag_api.id
  resource_id             = aws_api_gateway_resource.presign.id
  http_method             = aws_api_gateway_method.presign_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.presign.invoke_arn
}

resource "aws_lambda_permission" "presign_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.presign.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.rag_api.execution_arn}/*/*"
}

# ---------------------------------------------------------------------------
# /documents  (GET) — lists all indexed documents for the UI dropdown
# ---------------------------------------------------------------------------

resource "aws_lambda_function" "list_docs" {
  function_name    = "${var.project_name}-list-docs"
  role             = aws_iam_role.lambda_exec.arn
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  handler          = "list_handler.handler"
  runtime          = "python3.11"
  timeout          = 30
  memory_size      = 256

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.rag_index.name
      LOG_LEVEL      = "INFO"
    }
  }

  depends_on = [aws_cloudwatch_log_group.list_docs_logs]
}

resource "aws_cloudwatch_log_group" "list_docs_logs" {
  name              = "/aws/lambda/${var.project_name}-list-docs"
  retention_in_days = var.log_retention_days
}

resource "aws_api_gateway_resource" "documents" {
  rest_api_id = aws_api_gateway_rest_api.rag_api.id
  parent_id   = aws_api_gateway_rest_api.rag_api.root_resource_id
  path_part   = "documents"
}

resource "aws_api_gateway_method" "documents_get" {
  rest_api_id   = aws_api_gateway_rest_api.rag_api.id
  resource_id   = aws_api_gateway_resource.documents.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "documents_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.rag_api.id
  resource_id             = aws_api_gateway_resource.documents.id
  http_method             = aws_api_gateway_method.documents_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.list_docs.invoke_arn
}

resource "aws_lambda_permission" "list_docs_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.list_docs.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.rag_api.execution_arn}/*/*"
}

# ---------------------------------------------------------------------------
# Deployment & stage
# ---------------------------------------------------------------------------

resource "aws_api_gateway_deployment" "rag_api" {
  rest_api_id = aws_api_gateway_rest_api.rag_api.id

  # Force a new deployment whenever any integration changes
  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_integration.ingest_lambda,
      aws_api_gateway_integration.query_lambda,
      aws_api_gateway_integration.presign_lambda,
      aws_api_gateway_integration.documents_lambda,
      aws_api_gateway_integration.options_ingest,
      aws_api_gateway_integration.options_query,
      aws_api_gateway_integration.options_presign,
      aws_api_gateway_integration.options_documents,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_integration.ingest_lambda,
    aws_api_gateway_integration.query_lambda,
    aws_api_gateway_integration.presign_lambda,
    aws_api_gateway_integration.documents_lambda,
    aws_api_gateway_integration.options_ingest,
    aws_api_gateway_integration.options_query,
    aws_api_gateway_integration.options_presign,
    aws_api_gateway_integration.options_documents,
  ]
}

resource "aws_api_gateway_stage" "prod" {
  deployment_id = aws_api_gateway_deployment.rag_api.id
  rest_api_id   = aws_api_gateway_rest_api.rag_api.id
  stage_name    = "prod"

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway_logs.arn
  }
}

resource "aws_cloudwatch_log_group" "api_gateway_logs" {
  name              = "/aws/api-gateway/${var.project_name}"
  retention_in_days = var.log_retention_days
}

# ---------------------------------------------------------------------------
# Lambda permissions — allow API Gateway to invoke the functions
# ---------------------------------------------------------------------------

resource "aws_lambda_permission" "ingest_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingest.function_name
  principal     = "apigateway.amazonaws.com"
  # Restrict to this specific API only (best practice)
  source_arn = "${aws_api_gateway_rest_api.rag_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "query_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.query.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.rag_api.execution_arn}/*/*"
}
