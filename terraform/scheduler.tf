resource "aws_cloudwatch_event_rule" "daily_trigger" {
  name                = "eco-water-temps-daily-trigger"
  description         = "Triggers the ECOSTRESS initiator lambda daily"
  schedule_expression = "rate(1 day)"
}

resource "aws_cloudwatch_event_target" "trigger_lambda" {
  rule      = aws_cloudwatch_event_rule.daily_trigger.name
  target_id = "TriggerInitiatorLambda"
  arn       = aws_lambda_function.initiator_lambda.arn
}

resource "aws_lambda_permission" "allow_cloudwatch" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.initiator_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_trigger.arn
}

resource "aws_cloudwatch_event_rule" "task_poller_schedule" {
  name                = "${var.project_name}-task-poller-schedule"
  description         = "Triggers the task poller Lambda every 5 minutes"
  schedule_expression = "rate(5 minutes)"
}

resource "aws_cloudwatch_event_target" "task_poller_target" {
  rule      = aws_cloudwatch_event_rule.task_poller_schedule.name
  target_id = "TriggerTaskPollerLambda"
  arn       = aws_lambda_function.task_poller_lambda.arn
}

resource "aws_lambda_permission" "allow_cloudwatch_poller" {
  statement_id  = "AllowExecutionFromCloudWatchPoller"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.task_poller_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.task_poller_schedule.arn
}

# Landsat daily trigger (offset from ECOSTRESS at 06:00 UTC)
resource "aws_cloudwatch_event_rule" "landsat_daily_trigger" {
  name                = "${var.project_name}-landsat-daily-trigger"
  description         = "Triggers the Landsat initiator Lambda daily at 06:00 UTC"
  schedule_expression = "cron(0 6 * * ? *)"
}

resource "aws_cloudwatch_event_target" "landsat_trigger_target" {
  rule      = aws_cloudwatch_event_rule.landsat_daily_trigger.name
  target_id = "TriggerLandsatInitiatorLambda"
  arn       = aws_lambda_function.landsat_initiator_lambda.arn
}

resource "aws_lambda_permission" "allow_cloudwatch_landsat" {
  statement_id  = "AllowExecutionFromCloudWatchLandsat"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.landsat_initiator_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.landsat_daily_trigger.arn
}
