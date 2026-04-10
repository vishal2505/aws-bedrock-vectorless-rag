output "api_base_url" {
  description = "Base URL for the RAG REST API (append /ingest or /query)."
  value       = aws_api_gateway_stage.prod.invoke_url
}

output "ingest_endpoint" {
  description = "Full URL for POST /ingest."
  value       = "${aws_api_gateway_stage.prod.invoke_url}/ingest"
}

output "query_endpoint" {
  description = "Full URL for POST /query."
  value       = "${aws_api_gateway_stage.prod.invoke_url}/query"
}

output "documents_bucket_name" {
  description = "Name of the S3 bucket where you upload PDF/Markdown documents."
  value       = aws_s3_bucket.documents.bucket
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table that stores tree indexes and node texts."
  value       = aws_dynamodb_table.rag_index.name
}

output "ingest_lambda_name" {
  description = "Name of the ingest Lambda function (useful for direct invocation and log viewing)."
  value       = aws_lambda_function.ingest.function_name
}

output "query_lambda_name" {
  description = "Name of the query Lambda function."
  value       = aws_lambda_function.query.function_name
}

output "aws_region" {
  description = "AWS region where resources were deployed."
  value       = var.aws_region
}

output "website_url" {
  description = "URL of the S3 static website (landing page for demos)."
  value       = "http://${aws_s3_bucket_website_configuration.website.website_endpoint}"
}

output "website_bucket_name" {
  description = "Name of the S3 bucket hosting the frontend UI."
  value       = aws_s3_bucket.website.bucket
}
