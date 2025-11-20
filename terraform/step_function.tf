resource "aws_sfn_state_machine" "polling_machine" {
  name     = "${var.project_name}-polling-machine"
  role_arn = aws_iam_role.step_function_role.arn

  definition = jsonencode({
    Comment = "Poll AppEEARS task status and send to SQS when done"
    StartAt = "WaitDynamic"
    States = {
      WaitDynamic = {
        Type        = "Wait"
        SecondsPath = "$.wait_seconds"
        Next        = "CheckStatus"
      }
      CheckStatus = {
        Type       = "Task"
        Resource   = aws_lambda_function.status_checker_lambda.arn
        Parameters = {
          "task_id.$" = "$.task_id"
        }
        ResultPath = "$.status_result"
        Next       = "IsDone?"
        Retry = [
          {
            ErrorEquals = ["States.TaskFailed", "States.Timeout"]
            IntervalSeconds = 60
            MaxAttempts = 3
            BackoffRate = 2.0
          }
        ]
      }
      "IsDone?" = {
        Type = "Choice"
        Choices = [
          {
            Variable = "$.status_result.status"
            StringEquals = "done"
            Next = "ProcessManifest"
          },
          {
            Variable = "$.status_result.status"
            StringEquals = "error"
            Next = "FailState"
          }
        ]
        Default = "DoubleWait"
      }
      DoubleWait = {
        Type = "Pass"
        Parameters = {
          "task_id.$" = "$.task_id"
          "wait_seconds.$" = "States.MathAdd($.wait_seconds, $.wait_seconds)"
          "status_result.$" = "$.status_result"
        }
        Next = "WaitDynamic"
      }
      ProcessManifest = {
        Type       = "Task"
        Resource   = aws_lambda_function.manifest_processor_lambda.arn
        Parameters = {
          "task_id.$" = "$.task_id"
        }
        End = true
      }
      FailState = {
        Type = "Fail"
        Cause = "AppEEARS task failed"
        Error = "TaskFailed"
      }
    }
  })
}
