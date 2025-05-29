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
    Handles resending a verification code to a user.
    """
    try:
        body = json.loads(event.get('body', '{}'))
        username = body.get('username')

        if not username:
            return {
                'statusCode': 400,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS'
                },
                'body': json.dumps({'error': 'Username is required'})
            }

        # Resend the confirmation code
        cognito_client.resend_confirmation_code(
            ClientId=client_id,
            Username=username
        )

        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST, OPTIONS'
            },
            'body': json.dumps({'message': 'Verification code resent successfully'})
        }

    except ClientError as e:
        error_message = e.response.get('Error', {}).get('Message', 'An unknown error occurred')
        status_code = 400 # Default to 400, can be more specific based on error code
        
        # Specific error handling for resend_confirmation_code
        if e.response['Error']['Code'] == 'UserNotFoundException':
            error_message = 'User not found.'
        elif e.response['Error']['Code'] == 'InvalidParameterException':
            # This can happen if the user is already confirmed
            # Cognito's resend_confirmation_code throws InvalidParameterException if user is already confirmed
            # We can check the user status to be more specific if needed, but for now, a generic message.
            # Alternatively, could attempt to get user details and check status.
            # For simplicity, we'll return a message indicating the user might already be confirmed.
            # A better approach might be to check if the user is confirmed before attempting to resend.
            try:
                user_response = cognito_client.admin_get_user(
                    UserPoolId=user_pool_id,
                    Username=username # type: ignore
                )
                if user_response['UserStatus'] == 'CONFIRMED':
                    return {
                        'statusCode': 200, # Or 400 if you consider this a bad request
                        'headers': {
                            'Access-Control-Allow-Origin': '*',
                            'Access-Control-Allow-Headers': 'Content-Type',
                            'Access-Control-Allow-Methods': 'POST, OPTIONS'
                        },
                        'body': json.dumps({'message': 'User is already confirmed.'})
                    }
                error_message = 'Invalid parameter. The user might already be confirmed or the request is malformed.'

            except ClientError as inner_e:
                 # If admin_get_user also fails, stick to the original InvalidParameterException message
                 error_message = 'Invalid parameter or user state issue.'


        elif e.response['Error']['Code'] == 'LimitExceededException':
            error_message = 'Attempt limit exceeded, please try after some time.'
        # Add other specific error codes for resend_confirmation_code as needed
        # e.g., TooManyRequestsException, etc.

        # Fallback for NotAuthorizedException if it can occur and means something different here
        # For resend, NotAuthorizedException might mean the user is not in a state to receive a code (e.g. disabled)
        # However, typically UserNotFound or InvalidParameter (for already confirmed) are more common.
        elif e.response['Error']['Code'] == 'NotAuthorizedException':
             return {
                'statusCode': 403, 
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS'
                },
                'body': json.dumps({'error': 'Not authorized to perform this action.'})
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
