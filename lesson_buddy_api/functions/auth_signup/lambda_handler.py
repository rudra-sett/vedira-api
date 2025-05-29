import json
import boto3
import os
import re

cognito_client = boto3.client('cognito-idp')

USER_POOL_ID = os.environ.get('USER_POOL_ID')
CLIENT_ID = os.environ.get('CLIENT_ID')

# Basic email validation
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
# Basic phone number validation (E.164 format) - adjust as needed
PHONE_REGEX = r'^\+[1-9]\d{1,14}$'

def validate_password(password):
    """
    Validates password against common Cognito policies.
    Adjust to match your User Pool's specific password policy.
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain a lowercase letter."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain an uppercase letter."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain a digit."
    if not re.search(r"[!@#$%^&*()_+=\-[\]{};':\"\\|,.<>/?~`]", password): # Common symbols
        return False, "Password must contain a special symbol."
    return True, ""

def handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        email = body.get('email')
        phone_number = body.get('phone_number') # E.g., "+15555551212"
        password = body.get('password')

        if not all([email, phone_number, password]):
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Email, phone number, and password are required.'})
            }

        if not re.match(EMAIL_REGEX, email):
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Invalid email format.'})
            }

        if not re.match(PHONE_REGEX, phone_number):
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Invalid phone number format. Expected E.164 (e.g., +12223334444).'})
            }
        
        password_valid, password_error = validate_password(password)
        if not password_valid:
             return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': password_error})
            }

        response = cognito_client.sign_up(
            ClientId=CLIENT_ID,
            Username=email, # Using email as username
            Password=password,
            UserAttributes=[
                {'Name': 'email', 'Value': email},
                {'Name': 'phone_number', 'Value': phone_number},
                # Add any other required custom attributes here
            ]
            # ValidationData can be added if needed for pre sign-up lambda trigger
        )
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'message': 'User sign up successful. Please check your email/phone for verification code.',
                'userSub': response['UserSub'],
                'codeDeliveryDetails': response.get('CodeDeliveryDetailsList', response.get('CodeDeliveryDetails')) 
            })
        }

    except cognito_client.exceptions.UsernameExistsException:
        return {
            'statusCode': 409, # Conflict
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'User with this email already exists.'})
        }
    except cognito_client.exceptions.InvalidPasswordException as e:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': f"Invalid password: {str(e)}"})
        }
    except cognito_client.exceptions.TooManyRequestsException:
        return {
            'statusCode': 429,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Too many requests. Please try again later.'})
        }
    except Exception as e:
        print(f"Error during sign_up: {e}") # Log for debugging
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': f'An unexpected error occurred: {str(e)}'})
        }
