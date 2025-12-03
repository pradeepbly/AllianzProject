variable "aws_region" {
  description = "Region where resources will be created"
  type        = string
  default     = "us-east-1"
}

variable "table_name" {
  description = "Name of the DynamoDB table"
  type        = string
  default     = "VpcDetailsTable"
}

variable "lambda_function_name" {
  description = "Name of the Lambda function"
  type        = string
  default     = "VpcDetailsLambdaHandler"
}

variable "lambda_handler" {
  description = "Entrypoint of the Lambda function"
  type        = string
  default     = "app.main.handler"
}

variable "python_version" {
  description = "Python version for Lambda function"
  type        = string
  default     = "python3.12"
}

variable "lambda_filename" {
  description = "zip file for Lambda function"
  type        = string
  default     = "lambda.zip"
}

variable "lambda_timeout" {
  description = "Timeout in seconds for the Lambda function"
  type        = number
  default     = 30
}

variable "lambda_layer_name" {
  default = "ManageVpcDependenciesLayer"
}

variable "lambda_layer_zip" {
  description = "Path to the Lambda layer zip (containing dependencies)"
  default     = "layer.zip"
}