# ===========================================================================
# API Gateway CORS — OPTIONS preflight methods
#
# API Gateway v1 (REST API) with Lambda Proxy integration requires
# explicit OPTIONS methods with MOCK integrations for CORS preflight.
# The actual POST/GET response CORS headers are returned by the Lambda
# functions themselves (already done via Access-Control-Allow-* headers).
# ===========================================================================

locals {
  cors_allow_headers = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
  cors_allow_origin  = "'*'"
}

# ---------------------------------------------------------------------------
# Helper: reusable OPTIONS resources per endpoint
# ---------------------------------------------------------------------------

# ── /ingest OPTIONS ──────────────────────────────────────────────────────
resource "aws_api_gateway_method" "options_ingest" {
  rest_api_id   = aws_api_gateway_rest_api.rag_api.id
  resource_id   = aws_api_gateway_resource.ingest.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_ingest" {
  rest_api_id          = aws_api_gateway_rest_api.rag_api.id
  resource_id          = aws_api_gateway_resource.ingest.id
  http_method          = aws_api_gateway_method.options_ingest.http_method
  type                 = "MOCK"
  request_templates    = { "application/json" = "{\"statusCode\": 200}" }
}

resource "aws_api_gateway_method_response" "options_ingest_200" {
  rest_api_id = aws_api_gateway_rest_api.rag_api.id
  resource_id = aws_api_gateway_resource.ingest.id
  http_method = aws_api_gateway_method.options_ingest.http_method
  status_code = "200"
  response_models    = { "application/json" = "Empty" }
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_ingest" {
  rest_api_id = aws_api_gateway_rest_api.rag_api.id
  resource_id = aws_api_gateway_resource.ingest.id
  http_method = aws_api_gateway_method.options_ingest.http_method
  status_code = aws_api_gateway_method_response.options_ingest_200.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = local.cors_allow_headers
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = local.cors_allow_origin
  }
  depends_on = [aws_api_gateway_integration.options_ingest]
}

# ── /query OPTIONS ───────────────────────────────────────────────────────
resource "aws_api_gateway_method" "options_query" {
  rest_api_id   = aws_api_gateway_rest_api.rag_api.id
  resource_id   = aws_api_gateway_resource.query.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_query" {
  rest_api_id       = aws_api_gateway_rest_api.rag_api.id
  resource_id       = aws_api_gateway_resource.query.id
  http_method       = aws_api_gateway_method.options_query.http_method
  type              = "MOCK"
  request_templates = { "application/json" = "{\"statusCode\": 200}" }
}

resource "aws_api_gateway_method_response" "options_query_200" {
  rest_api_id = aws_api_gateway_rest_api.rag_api.id
  resource_id = aws_api_gateway_resource.query.id
  http_method = aws_api_gateway_method.options_query.http_method
  status_code = "200"
  response_models    = { "application/json" = "Empty" }
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_query" {
  rest_api_id = aws_api_gateway_rest_api.rag_api.id
  resource_id = aws_api_gateway_resource.query.id
  http_method = aws_api_gateway_method.options_query.http_method
  status_code = aws_api_gateway_method_response.options_query_200.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = local.cors_allow_headers
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = local.cors_allow_origin
  }
  depends_on = [aws_api_gateway_integration.options_query]
}

# ── /presign OPTIONS ─────────────────────────────────────────────────────
resource "aws_api_gateway_method" "options_presign" {
  rest_api_id   = aws_api_gateway_rest_api.rag_api.id
  resource_id   = aws_api_gateway_resource.presign.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_presign" {
  rest_api_id       = aws_api_gateway_rest_api.rag_api.id
  resource_id       = aws_api_gateway_resource.presign.id
  http_method       = aws_api_gateway_method.options_presign.http_method
  type              = "MOCK"
  request_templates = { "application/json" = "{\"statusCode\": 200}" }
}

resource "aws_api_gateway_method_response" "options_presign_200" {
  rest_api_id = aws_api_gateway_rest_api.rag_api.id
  resource_id = aws_api_gateway_resource.presign.id
  http_method = aws_api_gateway_method.options_presign.http_method
  status_code = "200"
  response_models    = { "application/json" = "Empty" }
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_presign" {
  rest_api_id = aws_api_gateway_rest_api.rag_api.id
  resource_id = aws_api_gateway_resource.presign.id
  http_method = aws_api_gateway_method.options_presign.http_method
  status_code = aws_api_gateway_method_response.options_presign_200.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = local.cors_allow_headers
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = local.cors_allow_origin
  }
  depends_on = [aws_api_gateway_integration.options_presign]
}

# ── /documents OPTIONS ───────────────────────────────────────────────────
resource "aws_api_gateway_method" "options_documents" {
  rest_api_id   = aws_api_gateway_rest_api.rag_api.id
  resource_id   = aws_api_gateway_resource.documents.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_documents" {
  rest_api_id       = aws_api_gateway_rest_api.rag_api.id
  resource_id       = aws_api_gateway_resource.documents.id
  http_method       = aws_api_gateway_method.options_documents.http_method
  type              = "MOCK"
  request_templates = { "application/json" = "{\"statusCode\": 200}" }
}

resource "aws_api_gateway_method_response" "options_documents_200" {
  rest_api_id = aws_api_gateway_rest_api.rag_api.id
  resource_id = aws_api_gateway_resource.documents.id
  http_method = aws_api_gateway_method.options_documents.http_method
  status_code = "200"
  response_models    = { "application/json" = "Empty" }
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_documents" {
  rest_api_id = aws_api_gateway_rest_api.rag_api.id
  resource_id = aws_api_gateway_resource.documents.id
  http_method = aws_api_gateway_method.options_documents.http_method
  status_code = aws_api_gateway_method_response.options_documents_200.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = local.cors_allow_headers
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = local.cors_allow_origin
  }
  depends_on = [aws_api_gateway_integration.options_documents]
}
