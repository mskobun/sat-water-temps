data "aws_ecr_image" "lambda_image" {
  repository_name = "${var.project_name}-lambda-images"
  image_tag       = "latest"
}

resource "aws_lambda_function" "initiator_lambda" {
  function_name = "${var.project_name}-initiator"
  role          = aws_iam_role.lambda_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.lambda_repo.repository_url}@${data.aws_ecr_image.lambda_image.image_digest}"
  
  image_config {
    command = ["initiator.handler"]
  }

  environment {
    variables = {
      APPEEARS_USER = var.appeears_user
      APPEEARS_PASS = var.appeears_pass
      STATE_MACHINE_ARN = aws_sfn_state_machine.polling_machine.arn
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

  environment {
    variables = {
      APPEEARS_USER = var.appeears_user
      APPEEARS_PASS = var.appeears_pass
      SUPABASE_URL  = var.supabase_url
      SUPABASE_KEY  = var.supabase_key
      BUCKET_NAME   = "multitifs" # Hardcoded for now, could be variable
    }
  }

  timeout     = 900 # 15 minutes max
  memory_size = 3008 # Increased memory for performance
}

# SQS Trigger for Processor Lambda
resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn = aws_sqs_queue.eco_processing_queue.arn
  function_name    = aws_lambda_function.processor_lambda.arn
  batch_size       = 1
}
