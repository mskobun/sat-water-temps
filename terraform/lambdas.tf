data "aws_ecr_image" "lambda_image" {
  repository_name = "${var.project_name}-lambda-images"
  image_tag       = "latest"
}

# CloudWatch Log Groups with retention (imported from auto-created groups)
resource "aws_cloudwatch_log_group" "initiator_logs" {
  name              = "/aws/lambda/${var.project_name}-initiator"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "status_checker_logs" {
  name              = "/aws/lambda/${var.project_name}-status-checker"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "processor_logs" {
  name              = "/aws/lambda/${var.project_name}-processor"
  retention_in_days = 30
}

resource "aws_lambda_function" "initiator_lambda" {
  function_name = "${var.project_name}-initiator"
  role          = aws_iam_role.lambda_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.lambda_repo.repository_url}@${data.aws_ecr_image.lambda_image.image_digest}"

  image_config {
    command = ["initiator.handler"]
  }

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      APPEEARS_USER         = var.appeears_user
      APPEEARS_PASS         = var.appeears_pass
      STATE_MACHINE_ARN     = aws_sfn_state_machine.polling_machine.arn
      D1_DATABASE_ID        = cloudflare_d1_database.main.id
      CLOUDFLARE_ACCOUNT_ID = var.cloudflare_account_id
      CLOUDFLARE_API_TOKEN  = var.cloudflare_api_token
    }
  }

  timeout = 300
}

resource "aws_lambda_function" "status_checker_lambda" {
  function_name = "${var.project_name}-status-checker"
  role          = aws_iam_role.lambda_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.lambda_repo.repository_url}@${data.aws_ecr_image.lambda_image.image_digest}"

  image_config {
    command = ["status_checker.handler"]
  }

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      APPEEARS_USER = var.appeears_user
      APPEEARS_PASS = var.appeears_pass
    }
  }

  timeout = 60
}

resource "aws_lambda_function" "processor_lambda" {
  function_name = "${var.project_name}-processor"
  role          = aws_iam_role.lambda_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.lambda_repo.repository_url}@${data.aws_ecr_image.lambda_image.image_digest}"

  image_config {
    command = ["processor.handler"]
  }

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      APPEEARS_USER         = var.appeears_user
      APPEEARS_PASS         = var.appeears_pass
      R2_ENDPOINT           = var.r2_endpoint
      R2_BUCKET_NAME        = var.r2_bucket_name
      R2_ACCESS_KEY_ID      = var.r2_access_key_id
      R2_SECRET_ACCESS_KEY  = var.r2_secret_access_key
      D1_DATABASE_ID        = cloudflare_d1_database.main.id
      CLOUDFLARE_ACCOUNT_ID = var.cloudflare_account_id
      CLOUDFLARE_API_TOKEN  = var.cloudflare_api_token
    }
  }

  timeout     = 900  # 15 minutes max
  memory_size = 3008 # Increased memory for performance
}

# Lambda Function URL for manual triggers from admin UI
resource "aws_lambda_function_url" "initiator_url" {
  function_name      = aws_lambda_function.initiator_lambda.function_name
  authorization_type = "AWS_IAM"
}

# Resource-based policies granting the Cloudflare invoker user permission to call the Function URL.
# Lambda Function URLs require BOTH InvokeFunctionUrl and InvokeFunction permissions.
resource "aws_lambda_permission" "allow_cf_invoker_url" {
  statement_id           = "AllowCfInvokerFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.initiator_lambda.function_name
  principal              = aws_iam_user.cloudflare_invoker.arn
  function_url_auth_type = "AWS_IAM"
}

resource "aws_lambda_permission" "allow_cf_invoker_function" {
  statement_id  = "AllowCfInvokerInvokeFunction"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.initiator_lambda.function_name
  principal     = aws_iam_user.cloudflare_invoker.arn
}

# IAM user for Cloudflare Workers to invoke the initiator Lambda
resource "aws_iam_user" "cloudflare_invoker" {
  name = "${var.project_name}-cf-invoker"
}

resource "aws_iam_user_policy" "cloudflare_invoker_policy" {
  name = "${var.project_name}-cf-invoker-policy"
  user = aws_iam_user.cloudflare_invoker.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["lambda:InvokeFunctionUrl", "lambda:InvokeFunction"]
      Resource = aws_lambda_function.initiator_lambda.arn
    }]
  })
}

resource "aws_iam_access_key" "cloudflare_invoker_key" {
  user = aws_iam_user.cloudflare_invoker.name
}

# SQS Trigger for Processor Lambda
resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn = aws_sqs_queue.eco_processing_queue.arn
  function_name    = aws_lambda_function.processor_lambda.arn
  batch_size       = 1
}
