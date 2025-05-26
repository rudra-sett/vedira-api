import json
import boto3
import os

sfn_client = boto3.client('stepfunctions')

def handler(event, context):
    """
    Checks the status of a Step Functions execution.
    """
    try:
        execution_arn = event.get('executionArn')
        if not execution_arn:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'executionArn is required'})
            }

        response = sfn_client.describe_execution(
            executionArn=execution_arn
        )

        status = response.get('status')
        output = response.get('output') # Output is available when SUCCEEDED

        is_complete = status == 'SUCCEEDED'
        is_failed = status == 'FAILED' or status == 'TIMED_OUT' or status == 'ABORTED'

        result = {
            'status': status,
            'isComplete': is_complete,
            'isFailed': is_failed,
        }

        if is_complete and output:
            try:
                result['output'] = json.loads(output)
            except json.JSONDecodeError:
                result['output'] = output # if output is not a valid JSON string
        elif is_failed:
            # Include error and cause if the execution failed
            error_details = response.get('error')
            cause_details = response.get('cause')
            if error_details:
                result['error'] = error_details
            if cause_details:
                result['cause'] = cause_details


        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
            },
            'body': json.dumps(result)
        }

    except Exception as e:
        print(f"Error checking execution status: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
            },
            'body': json.dumps({'error': str(e)})
        }
