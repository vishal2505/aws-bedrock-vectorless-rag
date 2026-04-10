# ===========================================================================
# S3 Static Website — Frontend UI
# ===========================================================================

locals {
  website_bucket_name = "${var.project_name}-website-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket" "website" {
  bucket        = local.website_bucket_name
  force_destroy = true
}

# Website buckets need public access enabled
resource "aws_s3_bucket_public_access_block" "website" {
  bucket                  = aws_s3_bucket.website.id
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "website" {
  bucket = aws_s3_bucket.website.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.website.arn}/*"
      }
    ]
  })

  # Policy requires public access block to be relaxed first
  depends_on = [aws_s3_bucket_public_access_block.website]
}

resource "aws_s3_bucket_website_configuration" "website" {
  bucket = aws_s3_bucket.website.id

  index_document { suffix = "index.html" }
  error_document { key    = "index.html" }   # SPA fallback
}

# ===========================================================================
# CORS on the Documents bucket
# Allows browsers to PUT files via presigned URLs from any origin
# ===========================================================================

resource "aws_s3_bucket_cors_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "HEAD"]
    allowed_origins = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}
