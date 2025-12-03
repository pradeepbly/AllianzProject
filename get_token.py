import boto3
import hmac
import hashlib
import base64
import os

def calculate_secret_hash(username, client_id, client_secret):
    """
    Generate the Cognito SECRET_HASH for a given username.

    AWS Cognito requires a SECRET_HASH when the app client is configured 
    with a client secret. The hash is computed using the HMAC-SHA256 
    algorithm and then Base64 encoded.

    Args:
        username (str): The username of the Cognito user.
        client_id (str): The Cognito App Client ID.
        client_secret (str): The Cognito App Client Secret.

    Returns:
        str: The Base64-encoded HMAC-SHA256 hash used as SECRET_HASH.

    Example:
        >>> calculate_secret_hash("testuser", "abc123", "secretkey")
        'b64EncodedHashString'
    """
    message = username + client_id
    dig = hmac.new(
        client_secret.encode('utf-8'),
        msg=message.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    return base64.b64encode(dig).decode()

# ---- Configuration Section ----
# Reads required environment variables for Cognito authentication.
# - CLIENT_ID: Cognito App Client ID
# - CLIENT_SECRET: Cognito App Client Secret
# - USER_NAME: Cognito username
# - USER_PASSWD: Cognito user password

CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
USERNAME = os.environ["USER_NAME"]
PASSWORD = os.environ["USER_PASSWD"]

# ---- Cognito Client Initialization ----
# Creates a boto3 client to interact with AWS Cognito Identity Provider.
client = boto3.client('cognito-idp', region_name='us-east-1')

# ---- Authentication Request ----
# Initiates authentication with Cognito using USER_PASSWORD_AUTH flow.
# The request includes:
#   - USERNAME
#   - PASSWORD
#   - SECRET_HASH (calculated via calculate_secret_hash)

response = client.initiate_auth(
   ClientId=CLIENT_ID,
   AuthFlow='USER_PASSWORD_AUTH',
   AuthParameters={
       'USERNAME': USERNAME,
       'PASSWORD': PASSWORD,
       'SECRET_HASH': calculate_secret_hash(USERNAME, CLIENT_ID, CLIENT_SECRET)
   }
)




# ---- Output Tokens ----
# On successful authentication, prints the tokens returned by Cognito:
#   - Access Token
#   - ID Token
#   - Refresh Token
#print("\n FULL COGNITO RESPONSE:\n", response)
print("Access Token:", response['AuthenticationResult']['AccessToken'])
print("ID Token:", response['AuthenticationResult']['IdToken'])
print("Refresh Token:", response['AuthenticationResult']['RefreshToken'])
