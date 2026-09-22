# ─────────────────────────────────────────────────────────────────────────────
# EventBridge – EC2 Instance State Change Logging (Feature 7)
# Captures start/stop/terminate/reboot events and sends them to Lambda
# for audit logging in S3. Provides a complete instance lifecycle trail.
# EventBridge default bus is FREE.
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_cloudwatch_event_rule" "ec2_state_change" {
  name        = "${var.project_name}-ec2-state-change"
  description = "Captures EC2 instance state change events for audit logging"

  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["EC2 Instance State-change Notification"]
    detail = {
      instance-id = [aws_instance.web_server.id]
    }
  })

  tags = { Project = var.project_name }
}

# ── Route state-change events to the Lambda for S3 audit logging ─────────
resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.ec2_state_change.name
  target_id = "${var.project_name}-lambda"
  arn       = aws_lambda_function.remediation.arn
}

# ── Permission: allow EventBridge to invoke the Lambda ────────────────────
resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.remediation.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ec2_state_change.arn
}

# ─────────────────────────────────────────────────────────────────────────────
# EventBridge – 1 Minute Cron for Health Manager
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_cloudwatch_event_rule" "health_manager_cron" {
  name                = "${var.project_name}-health-manager-cron"
  description         = "Triggers the self-healing health manager every 1 minute"
  schedule_expression = "rate(1 minute)"
  tags                = { Project = var.project_name }
}

resource "aws_cloudwatch_event_target" "health_manager_target" {
  rule      = aws_cloudwatch_event_rule.health_manager_cron.name
  target_id = "${var.project_name}-health-manager-target"
  arn       = aws_lambda_function.health_manager.arn
}

resource "aws_lambda_permission" "allow_health_manager_cron" {
  statement_id  = "AllowEventBridgeInvokeHealthManager"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.health_manager.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.health_manager_cron.arn
}

# ─────────────────────────────────────────────────────────────────────────────
# EventBridge – 5 Minute Cron for Predictive Failure Detection
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_cloudwatch_event_rule" "predictor_cron" {
  name                = "${var.project_name}-predictor-cron"
  description         = "Triggers predictive failure detection every 5 minutes"
  schedule_expression = "rate(5 minutes)"
  tags                = { Project = var.project_name }
}

resource "aws_cloudwatch_event_target" "predictor_target" {
  rule      = aws_cloudwatch_event_rule.predictor_cron.name
  target_id = "${var.project_name}-predictor-target"
  arn       = aws_lambda_function.predictor.arn
}

resource "aws_lambda_permission" "allow_predictor_cron" {
  statement_id  = "AllowEventBridgeInvokePredictor"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.predictor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.predictor_cron.arn
}
