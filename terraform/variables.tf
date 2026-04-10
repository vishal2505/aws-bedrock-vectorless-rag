variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "ap-southeast-1"
}

variable "project_name" {
  description = "Prefix applied to every resource name for easy identification."
  type        = string
  default     = "vectorless-rag"

  validation {
    condition     = can(regex("^[a-z0-9-]{3,24}$", var.project_name))
    error_message = "project_name must be 3-24 characters: lowercase letters, digits, hyphens."
  }
}

variable "bedrock_model_id" {
  description = <<-EOT
    Amazon Bedrock foundation model ID used for all LLM calls.
    Must be enabled in the target region via the AWS console before use.
    Examples:
      anthropic.claude-3-haiku-20240307-v1:0   (fast, cheap — default)
      anthropic.claude-3-sonnet-20240229-v1:0  (higher quality)
  EOT
  type    = string
  default = "anthropic.claude-3-haiku-20240307-v1:0"
}

variable "lambda_timeout" {
  description = <<-EOT
    Lambda function timeout in seconds.
    Ingestion of large PDFs requires time for multiple Bedrock summary calls.
    Default: 300s (5 minutes).
  EOT
  type    = number
  default = 300
}

variable "lambda_memory_size" {
  description = "Lambda function memory in MB. More memory also means more vCPU."
  type        = number
  default     = 512
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention period in days."
  type        = number
  default     = 14
}

variable "max_retrieved_nodes" {
  description = "Maximum number of tree nodes fetched per query (caps context size)."
  type        = number
  default     = 5
}

variable "allowed_cors_origin" {
  description = "Value for Access-Control-Allow-Origin response header (CORS). Use '*' for development."
  type        = string
  default     = "*"
}
