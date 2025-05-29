import json
import os
import boto3
from botocore.exceptions import ClientError

# Initialize AWS clients (consider moving to a shared utility if used in multiple lambdas)
cognito_client = boto3.client('cognito-idp')
dynamodb = boto3.resource('dynamodb')
user_pool_id = os.environ.get('USER_POOL_ID')
client_id = os.environ.get('USER_POOL_CLIENT_ID')
# users_table_name = os.environ.get('USERS_TABLE_NAME')
# users_table = dynamodb.Table(users_table_name)

def lambda_handler(event, context):
    """
    Handles user verification using a confirmation code.
    """
    try:
        body = json.loads(event.get('body', '{}'))
        username = body.get('username')
        confirmation_code = body.get('confirmation_code')

        if not username or not confirmation_code:
            return {
                'statusCode': 400,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS'
                },
                'body': json.dumps({'error': 'Username and confirmation_code are required'})
            }

        # Confirm the user in Cognito
        cognito_client.confirm_sign_up(
            ClientId=client_id,
            Username=username,
            ConfirmationCode=confirmation_code
        )

        # Optionally, update user status in DynamoDB if you track verification there
        # For example, set a 'verified' attribute to True
        # users_table.update_item(
        #     Key={'username': username},
        #     UpdateExpression='SET email_verified = :val',
        #     ExpressionAttributeValues={':val': True}
        # )

        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST, OPTIONS'
            },
            'body': json.dumps({'message': 'User verified successfully'})
        }

    except ClientError as e:
        error_message = e.response.get('Error', {}).get('Message', 'An unknown error occurred')
        status_code = 400 # Default to 400, can be more specific based on error code
        if e.response['Error']['Code'] == 'CodeMismatchException':
            error_message = 'Invalid verification code.'
        elif e.response['Error']['Code'] == 'ExpiredCodeException':
            error_message = 'Verification code has expired.'
        elif e.response['Error']['Code'] == 'UserNotFoundException':
            error_message = 'User not found.'
        elif e.response['Error']['Code'] == 'NotAuthorizedException': # Already confirmed
             return {
                'statusCode': 200, # Or a different code like 202 if you want to indicate "already done"
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS'
                },
                'body': json.dumps({'message': 'User already verified'})
            }


        return {
            'statusCode': status_code,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST, OPTIONS'
            },
            'body': json.dumps({'error': error_message, 'details': str(e)})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST, OPTIONS'
            },
            'body': json.dumps({'error': 'An internal server error occurred', 'details': str(e)})
        }
