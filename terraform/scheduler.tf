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
