resource "aws_cloudwatch_log_group" "manifest_processor_logs" {
  name              = "/aws/lambda/${var.project_name}-manifest-processor"
  retention_in_days = 30
}

resource "aws_lambda_function" "manifest_processor_lambda" {
  function_name = "${var.project_name}-manifest-processor"
  role          = aws_iam_role.lambda_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.lambda_repo.repository_url}@${data.aws_ecr_image.lambda_image.image_digest}"

  image_config {
    command = ["manifest_processor.handler"]
  }

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      APPEEARS_USER         = var.appeears_user
      APPEEARS_PASS         = var.appeears_pass
      SQS_QUEUE_URL         = aws_sqs_queue.eco_processing_queue.url
      D1_DATABASE_ID        = cloudflare_d1_database.main.id
      CLOUDFLARE_ACCOUNT_ID = var.cloudflare_account_id
      CLOUDFLARE_API_TOKEN  = var.cloudflare_api_token
    }
  }

  timeout = 300
}
