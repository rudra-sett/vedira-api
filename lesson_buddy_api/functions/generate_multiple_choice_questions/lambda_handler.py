import json
import os
from typing import Dict, Any, List, Union
from urllib import request, parse, error as urllib_error
import time
# import boto3 # Placeholder if we need AWS SDK later, e.g., for Bedrock

# bedrock_runtime = boto3.client(service_name='bedrock-runtime') # Placeholder

def get_api_info(model):
    if model == 'gemini-2.5-flash':
        url = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
        api_key = os.environ['API_KEY']
        return url, api_key, 'gemini-2.5-flash-preview-04-17'
    if model == 'gemini-2.5-pro':
        url = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
        api_key = os.environ['API_KEY']
        return url, api_key, 'gemini-2.5-pro-preview-05-06'
    if model == 'claude-4-sonnet':
        url = 'http://Bedroc-Proxy-xVtSm3tV6xYe-1727257641.us-east-1.elb.amazonaws.com/api/v1/chat/completions'
        api_key = os.environ['BEDROCK_API_KEY']
        return url, api_key, 'us.anthropic.claude-sonnet-4-20250514-v1:0'
    if model == 'claude-3.7-sonnet':
        url = 'http://Bedroc-Proxy-xVtSm3tV6xYe-1727257641.us-east-1.elb.amazonaws.com/api/v1/chat/completions'
        api_key = os.environ['BEDROCK_API_KEY']
        return url, api_key, 'us.anthropic.claude-3-7-sonnet-20250219-v1:0'
    if model == 'claude-3.5-haiku':
        url = 'http://Bedroc-Proxy-xVtSm3tV6xYe-1727257641.us-east-1.elb.amazonaws.com/api/v1/chat/completions'
        api_key = os.environ['BEDROCK_API_KEY']
        return url, api_key, 'us.anthropic.claude-3-5-haiku-20241022-v1:0'
    if model == 'gemini-2.0-flash':
        url = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
        api_key = os.environ['API_KEY']
        return url, api_key, 'gemini-2.0-flash-001'
    if model == 'gemini-2.0-flash-lite':
        url = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
        api_key = os.environ['API_KEY']
        return url, api_key, 'gemini-2.0-flash-lite-001'
    # Fallback or error for unknown model
    raise ValueError(f"Unsupported model: {model}")

def call_model(system_prompt, prompt, messages=None, output_format=None, tools=None, model='gemini-2.5-flash'):
    url, api_key, model_identifier = get_api_info(model)

    data = {
        "model": model_identifier,
        "messages": [],
        "max_tokens": 8192 # Max tokens for Gemini Flash according to docs, adjust if needed for others
    }

    data['messages'].append({"role": "system", "content": system_prompt})

    if messages is not None:
        data['messages'].extend(messages)
    
    data['messages'].append({"role": "user", "content": prompt})
    
    if output_format:
        data['response_format'] = {
            "type": "json_schema", # Assuming Gemini-like API, OpenAI uses "type": "json_object"
            "json_schema": {       # For OpenAI, this would be under a "schema" key if using a more complex schema
                "name": "output",  # Name might not be universally required
                "schema": output_format  
            }
        }
        # For Anthropic through Bedrock proxy, if it supports structured output,
        # the format might differ. The current proxy seems to emulate OpenAI.

    if tools:
        data['tools'] = tools

    data_bytes = json.dumps(data).encode('utf-8')
    
    max_retries = 5
    base_delay = 1
    max_delay = 10
    
    for attempt in range(max_retries + 1):
        req = request.Request(url, data=data_bytes, method='POST') # Ensure POST
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', f'Bearer {api_key}')
        
        try:
            with request.urlopen(req) as resp:
                if resp.status == 200:
                    content = resp.read()
                    output = json.loads(content)
                    print("LLM Raw Output:", output) # For debugging
                    if output.get('choices') and output['choices'][0].get('message'):
                        return output['choices'][0]['message']
                    else: # Handle cases like Anthropic via Bedrock proxy if structure differs
                        # This part might need adjustment based on actual proxy response for errors/structure
                        print(f"Unexpected LLM response structure: {output}")
                        # Attempt to find content if structure is slightly different (e.g. Claude on Bedrock)
                        if output.get('content') and isinstance(output['content'], list) and output['content'][0].get('text'):
                             return {"role": "assistant", "content": output['content'][0]['text']} # Adapt to OpenAI-like structure
                        return {"role": "assistant", "content": json.dumps(output)} # Fallback to stringified output
                else:
                    error_content = resp.read().decode('utf-8')
                    print(f"HTTP Error: {resp.status} - {resp.reason}. Response: {error_content}")
                    # For 4xx errors, typically don't retry unless specific (e.g. rate limit 429)
                    if 400 <= resp.status < 500 and resp.status != 429:
                        raise Exception(f"HTTP Client Error: {resp.status} - {error_content}")
                    raise urllib_error.HTTPError(url, resp.status, error_content, resp.headers, None)
                    
        except Exception as e:
            if attempt == max_retries:
                print(f"Error: Final attempt failed after {max_retries} retries: {e}")
                return None # Or raise the exception: raise
            
            # Check for specific retryable errors
            is_http_error = isinstance(e, urllib_error.HTTPError)
            is_url_error = isinstance(e, urllib_error.URLError) # General network issues
                
            if (is_http_error and e.code in [500, 502, 503, 504, 429]) or is_url_error: # Added 429 for rate limits
                delay = min(base_delay * (2 ** attempt), max_delay)
                jitter = delay * 0.1 * (0.5 - (0.5 * attempt / max_retries))
                sleep_time = delay + jitter
                
                print(f"Attempt {attempt + 1} failed. Retrying in {sleep_time:.2f} seconds... Error: {e}")
                time.sleep(sleep_time)
            else:
                print(f"Non-retryable error: {e}")
                return None # Or raise the exception: raise
    return None # Should be unreachable if retries exhaust or an error is re-raised

def generate_questions_from_content(lesson_content_markdown: str) -> List[Dict[str, Any]]:
    """
    Generates multiple choice questions from lesson content using an LLM.
    """
    system_prompt = """
    You are an expert in creating educational assessments. Based on the provided lesson content,
    generate a list of 3 to 5 multiple-choice questions. Each question should have exactly 4 options,
    a single correct answer (which must be one of the provided options), and a brief explanation for why that answer is correct.
    Ensure the questions accurately test understanding of the key concepts in the lesson.
    Output the questions in the specified JSON format.
    """
    user_prompt = f"Here is the lesson content:\n\n{lesson_content_markdown}\n\nPlease generate 3 to 5 multiple-choice questions based on this content."

    question_schema = {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "The text of the multiple-choice question."},
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 4,
                            "maxItems": 4,
                            "description": "An array of exactly 4 potential answer strings."
                        },
                        "answer": {"type": "string", "description": "The correct answer, which must exactly match one of the strings in the 'options' array."},
                        "explanation": {"type": "string", "description": "A brief explanation of why the answer is correct."}
                    },
                    "required": ["question", "options", "answer", "explanation"]
                },
                "description": "A list of 3 to 5 multiple-choice questions."
            }
        },
        "required": ["questions"]
    }

    model_output = call_model(
        system_prompt=system_prompt,
        prompt=user_prompt,
        output_format=question_schema,
        model='gemini-2.5-flash' # Using a capable model for JSON generation
    )

    if model_output and 'content' in model_output and model_output['content']:
        try:
            # The 'content' from the LLM is expected to be a JSON string
            # that matches the 'question_schema'
            questions_data_str = model_output['content']
            print(f"LLM content string for questions: {questions_data_str}")
            questions_data = json.loads(questions_data_str)
            
            if "questions" in questions_data and isinstance(questions_data["questions"], list):
                valid_questions = []
                for q_item in questions_data["questions"]:
                    # Basic validation
                    if not isinstance(q_item, dict):
                        print(f"Warning: Question item is not a dictionary: {q_item}")
                        continue
                    if not all(k in q_item for k in ["question", "options", "answer", "explanation"]):
                        print(f"Warning: Question item missing required keys: {q_item}")
                        continue
                    if not isinstance(q_item.get("options"), list) or len(q_item["options"]) != 4:
                         print(f"Warning: Question options malformed or not 4 options: {q_item.get('options')}")
                         continue
                    if q_item.get("answer") not in q_item.get("options", []):
                        print(f"Warning: Answer '{q_item.get('answer')}' not in options {q_item.get('options')} for question '{q_item.get('question')}'")
                        # Optionally, try to find the closest match or skip
                        continue
                    valid_questions.append(q_item)
                
                if not valid_questions:
                    print("Warning: No valid questions were parsed from LLM response.")
                return valid_questions
            else:
                print(f"Error: 'questions' key not found or not a list in LLM response JSON: {questions_data}")
                return []
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from LLM: {e}")
            print(f"LLM raw content string: {model_output['content']}")
            return []
        except TypeError as e:
            print(f"Error processing LLM content (TypeError, possibly model_output['content'] is None or not string): {e}")
            print(f"LLM model_output: {model_output}")
            return []
    else:
        print("Error: LLM call failed or did not return content.")
        if model_output:
            print(f"LLM model_output: {model_output}")
        return []

def lambda_handler(event: Union[Dict[str, Any], str], context: Any) -> Dict[str, Any]:
    """
    Lambda handler function.
    Expects input that includes lesson markdown content.
    Generates multiple-choice questions and adds them to the data.
    """
    print(f"Received event: {json.dumps(event)}")

    try:
        data_payload: Dict[str, Any] = {}
        lesson_markdown: str = ""

        if isinstance(event, dict):
            data_payload = {k: v for k, v in event.items()} # Shallow copy
            
            # Determine the key for markdown content
            # Common keys from previous steps in a potential state machine
            markdown_keys = ['markdown_content', 'fixed_markdown', 'generated_markdown', 'lesson_content']
            for key in markdown_keys:
                if key in data_payload:
                    lesson_markdown = str(data_payload[key])
                    break
            
            if not lesson_markdown and 'body' in data_payload and isinstance(data_payload['body'], dict) and 'lesson_content' in data_payload['body']:
                 # Handle case where lesson_content might be nested if coming from generate_lesson_content directly
                 lesson_markdown = str(data_payload['body']['lesson_content'])


            if not lesson_markdown:
                 # If event is a dict but no markdown key is found, this is an issue.
                raise ValueError("Input dictionary is missing a recognized markdown key (e.g., 'markdown_content', 'fixed_markdown', 'generated_markdown', 'lesson_content')")
        
        elif isinstance(event, str):
            lesson_markdown = event
            data_payload = {'markdown_content': lesson_markdown} # Initialize data_payload
        
        else:
            raise ValueError(f"Unexpected event type: {type(event)}. Expected dict or str.")

        if not lesson_markdown.strip():
             raise ValueError("Unable to extract or received empty lesson markdown content from the event.")

        print(f"Extracted lesson markdown (first 100 chars): {lesson_markdown[:100]}...")
        multiple_choice_questions: List[Dict[str, Any]] = generate_questions_from_content(lesson_markdown)
        
        if not multiple_choice_questions:
            print("Warning: No multiple choice questions were generated. Proceeding with an empty list.")
            # Decide if this should be an error or if an empty list is acceptable.
            # For now, allowing empty list.
            
        data_payload['multiple_choice_questions'] = multiple_choice_questions
        
        print(f"Generated questions, final output payload (first 200 chars of questions): {json.dumps(data_payload)[:200]}...")

        return data_payload

    except Exception as e:
        print(f"Error in generate_multiple_choice_questions lambda_handler: {str(e)}")
        # Re-raise to let Step Functions (or caller) handle it.
        # Consider specific error reporting if this integrates with a larger system.
        raise

if __name__ == '__main__':
    # Mock environment variables for local testing if not set externally
    os.environ.setdefault('API_KEY', 'your_gemini_api_key_here_if_not_set') # Replace with a real key for actual calls
    os.environ.setdefault('BEDROCK_API_KEY', 'your_bedrock_api_key_here_if_not_set')

    print("\n--- Testing with sample_event_from_fix_markdown ---")
    sample_event_from_fix_markdown = {
       "lesson_id": "lesson123",
       "chapter_id": "chapter01",
       "course_id": "courseABC",
       "markdown_content": "# Chapter 1: Introduction to Python\nPython is a versatile language. You can make web apps, do data science, or automate tasks.\n\nKey concepts:\n- Variables\n- Data Types (integers, strings, lists)\n- Basic syntax"
    }
    # To prevent actual API calls during this simulated test, you might mock call_model or ensure API keys are dummy values
    # For a true local test, ensure API keys are valid and models are accessible.
    try:
        result_fix_style = lambda_handler(sample_event_from_fix_markdown, None)
        print(json.dumps(result_fix_style, indent=2))
    except Exception as e:
        print(f"Test failed for sample_event_from_fix_markdown: {e}")


    print("\n--- Testing with sample_event_direct_markdown (string input) ---")
    sample_event_direct_markdown = "# Chapter 2: Advanced Python\nThis lesson covers decorators and generators.\nDecorators allow you to modify functions or methods in a clean way.\nGenerators are useful for creating iterators with a simpler syntax."
    try:
        result_direct = lambda_handler(sample_event_direct_markdown, None) 
        print(json.dumps(result_direct, indent=2))
    except Exception as e:
        print(f"Test failed for sample_event_direct_markdown: {e}")

    print("\n--- Testing with sample_event_from_generate_lesson_content_style ---")
    # This simulates output from a previous 'generate_lesson_content' step
    sample_event_from_generate_lesson_content_style = {
        "lesson_id": "lesson456",
        "chapter_id": "chapter02",
        "course_id": "courseXYZ",
        "lesson_content": "## Topic: Object-Oriented Programming\nOOP involves classes, objects, inheritance, and polymorphism. Python supports OOP principles.", # Key for markdown
        "original_course_plan_details": "Some other data from course plan"
    }
    try:
        result_gen_style = lambda_handler(sample_event_from_generate_lesson_content_style, None)
        print(json.dumps(result_gen_style, indent=2))
    except Exception as e:
        print(f"Test failed for sample_event_from_generate_lesson_content_style: {e}")


    print("\n--- Testing with event missing a known markdown key ---")
    sample_event_missing_key = {
        "lesson_id": "lesson789",
        "chapter_id": "chapter03",
        "some_other_data": "value"
    }
    try:
        lambda_handler(sample_event_missing_key, None)
    except ValueError as e:
        print(f"Caught expected error for missing key: {e}")
    except Exception as e:
        print(f"Test failed with unexpected error for missing key: {e}")


    print("\n--- Testing with unexpected event type (e.g., integer) ---")
    sample_event_wrong_type = 12345
    try:
        lambda_handler(sample_event_wrong_type, None) # type: ignore
    except ValueError as e:
        print(f"Caught expected error for wrong type: {e}")
    except Exception as e:
        print(f"Test failed with unexpected error for wrong type: {e}")

    print("\n--- Testing with empty markdown string ---")
    sample_event_empty_markdown = {
       "lesson_id": "lesson101",
       "markdown_content": "   " # Whitespace only
    }
    try:
        lambda_handler(sample_event_empty_markdown, None)
    except ValueError as e:
        print(f"Caught expected error for empty markdown: {e}")
    except Exception as e:
        print(f"Test failed with unexpected error for empty markdown: {e}")
