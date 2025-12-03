resource "aws_cognito_user_pool" "this" {
  name = "allianz_api-user-pool"
}

resource "aws_cognito_user_pool_client" "this" {
  name                                 = "allianz_api-swagger-client"
  user_pool_id                         = aws_cognito_user_pool.this.id
  explicit_auth_flows                  = ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  supported_identity_providers         = ["COGNITO"]
  generate_secret                      = true
  allowed_oauth_flows                  = ["code", "implicit"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  callback_urls                        = ["${aws_apigatewayv2_stage.this.invoke_url}docs"]
}

resource "aws_cognito_user_pool_domain" "this" {
  domain       = "allianz-api-demo-auth"
  user_pool_id = aws_cognito_user_pool.this.id
}

resource "aws_dynamodb_table" "this" {
  name         = var.table_name
  billing_mode = "PAY_PER_REQUEST"

  hash_key = "VpcId"

  attribute {
    name = "VpcId"
    type = "S"
  }

  tags = {
    Environment = "dev"
    Name        = var.table_name
  }
}


resource "aws_iam_role" "this" {
  name = "lambda-vpc-deployment-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "lambda.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
}


resource "aws_iam_policy" "this" {
  name        = "lambdavpc-dynamic-policy"
  description = "Lambda policy DynamoDB & log ARNs"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = ["logs:CreateLogGroup"],
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
      },
      {
        Effect = "Allow",
        Action = [
          "ec2:CreateVpc",
          "ec2:ModifyVpcAttribute",
          "ec2:DeleteVpc",
          "ec2:CreateTags",
          "ec2:CreateInternetGateway",
          "ec2:AttachInternetGateway",
          "ec2:DetachInternetGateway",
          "ec2:DeleteInternetGateway",
          "ec2:CreateRouteTable",
          "ec2:DeleteRouteTable",
          "ec2:CreateRoute",
          "ec2:CreateSubnet",
          "ec2:AssociateRouteTable",
          "ec2:DisassociateRouteTable",
          "ec2:DeleteSubnet",
          "ec2:DescribeRouteTables",
          "ec2:DescribeInternetGateways"
        ],
        Resource = "*"
      },
      {
        Effect   = "Allow",
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"],
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:*"
      },
      {
        Effect = "Allow",
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:DeleteItem",
          "dynamodb:Scan",
          "dynamodb:UpdateItem"
        ],
        Resource = aws_dynamodb_table.this.arn
      }
    ]
  })
}


resource "aws_iam_role_policy_attachment" "this" {
  role       = aws_iam_role.this.name
  policy_arn = aws_iam_policy.this.arn
}


resource "aws_lambda_layer_version" "this" {
  layer_name          = var.lambda_layer_name
  filename            = var.lambda_layer_zip
  compatible_runtimes = [var.python_version]
  description         = "Dependencies for ManageVpcApi Lambda"
}


resource "aws_lambda_function" "this" {
  function_name = var.lambda_function_name
  handler       = var.lambda_handler
  runtime       = var.python_version
  role          = aws_iam_role.this.arn  
  timeout       = var.lambda_timeout
  filename      = var.lambda_filename

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.this.name
      DB_REGION  = var.aws_region
    }
  }
  layers = [aws_lambda_layer_version.this.arn]

  depends_on = [
    aws_dynamodb_table.this,
    aws_lambda_layer_version.this
  ]
}


resource "aws_apigatewayv2_api" "this" {
  name          = "VpcDeploymentLambdaAPI"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_authorizer" "this" {
  api_id           = aws_apigatewayv2_api.this.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]

  name = "cognito-jwt-auth"

  jwt_configuration {
    audience = [aws_cognito_user_pool_client.this.id]
    issuer   = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.this.id}"
  }
}

resource "aws_apigatewayv2_integration" "this" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.this.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "this" {
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = "ANY /{proxy+}"
  target             = "integrations/${aws_apigatewayv2_integration.this.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.this.id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_stage" "this" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "this" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}
