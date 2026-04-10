# ===========================================================================
# IAM — API Gateway CloudWatch logging role (account-level setting)
#
# API Gateway requires a single IAM role to be registered at the AWS account
# level before any stage can write access logs to CloudWatch Logs.
# ===========================================================================

resource "aws_iam_role" "apigw_cloudwatch" {
  name        = "${var.project_name}-apigw-cloudwatch"
  description = "Allows API Gateway to push logs to CloudWatch Logs"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "APIGatewayAssumeRole"
        Effect    = "Allow"
        Principal = { Service = "apigateway.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "apigw_cloudwatch" {
  role       = aws_iam_role.apigw_cloudwatch.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}

# Register the role at account level — required once per AWS account per region
resource "aws_api_gateway_account" "main" {
  cloudwatch_role_arn = aws_iam_role.apigw_cloudwatch.arn

  depends_on = [aws_iam_role_policy_attachment.apigw_cloudwatch]
}

# ===========================================================================
# IAM — Lambda execution role and inline policies
# ===========================================================================

# ---------------------------------------------------------------------------
# Execution role (trust relationship)
# ---------------------------------------------------------------------------

resource "aws_iam_role" "lambda_exec" {
  name        = "${var.project_name}-lambda-exec"
  description = "Execution role shared by all ${var.project_name} Lambda functions"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "LambdaAssumeRole"
        Effect    = "Allow"
        Principal = { Service = "lambda.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# Managed policy: basic Lambda execution (CloudWatch Logs)
# ---------------------------------------------------------------------------

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# ---------------------------------------------------------------------------
# Inline policy: S3 access (read documents, no public write)
# ---------------------------------------------------------------------------

resource "aws_iam_role_policy" "lambda_s3" {
  name = "${var.project_name}-lambda-s3"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadWriteDocuments"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
        ]
        Resource = [
          aws_s3_bucket.documents.arn,
          "${aws_s3_bucket.documents.arn}/*",
        ]
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# Inline policy: DynamoDB access (read/write the RAG index)
# ---------------------------------------------------------------------------

resource "aws_iam_role_policy" "lambda_dynamodb" {
  name = "${var.project_name}-lambda-dynamodb"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "RagIndexReadWrite"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:BatchWriteItem",
          "dynamodb:BatchGetItem",
          "dynamodb:Query",
          "dynamodb:Scan",
        ]
        Resource = aws_dynamodb_table.rag_index.arn
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# Inline policy: Lambda self-invocation
#
# The ingest Lambda re-invokes itself asynchronously (InvocationType=Event)
# to work around API Gateway's hard 29-second timeout. It needs permission
# to call lambda:InvokeFunction on functions in this project.
# ---------------------------------------------------------------------------

resource "aws_iam_role_policy" "lambda_self_invoke" {
  name = "${var.project_name}-lambda-self-invoke"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SelfInvoke"
        Effect = "Allow"
        Action = "lambda:InvokeFunction"
        Resource = "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:${var.project_name}-*"
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# Inline policy: Bedrock model invocation
#
# Note: bedrock:InvokeModel covers both the InvokeModel and Converse APIs.
# The resource ARN uses the foundation-model path for direct model access.
# If you switch to cross-region inference profiles, add:
#   arn:aws:bedrock:*:*:inference-profile/*
# ---------------------------------------------------------------------------

resource "aws_iam_role_policy" "lambda_bedrock" {
  name = "${var.project_name}-lambda-bedrock"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "InvokeBedrockModel"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
        ]
        Resource = [
          # Foundation model (direct access)
          "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_model_id}",
          # Cross-region inference profiles (needed if model ID contains a region prefix)
          "arn:aws:bedrock:*:${data.aws_caller_identity.current.account_id}:inference-profile/*",
        ]
      }
    ]
  })
}
