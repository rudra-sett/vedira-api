import json
from urllib import request, parse, error as urllib_error # Added urllib_error
import boto3
import time
import os

def lambda_handler(event, context):
    # try:
    print(event)
    
    data = event['body']
    course_plan = data['course_plan']
    chapter_id = data['chapter_id']
    lesson_id = data['lesson_id']

    lesson_data = {}
    chapter_info = {}

    for c, chapter in enumerate(course_plan["chapters"]):
        if chapter['id'] == chapter_id:      
            chapter_info['title'] = chapter['title']
            chapter_info['description'] = chapter['description']
            for l, lesson in enumerate(chapter['lessons']):
                if lesson['id'] == lesson_id:
                    lesson_data = lesson
                    course_plan['chapters'][c]['lessons'][l]['generated'] = True                    
    
    lesson_content = main_agent(course_plan, lesson_data, chapter_info)

    # S3 saving will be handled by the fix_lesson_markdown Lambda
    # Ensure all necessary IDs and the content are returned for the next step.
    return {
        "chapter_id" : chapter_id,
        "lesson_id" : lesson_id,
        "lesson_content": lesson_content,
        "course_id": course_plan['CourseID'] 
    }


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
    # maybe try other LLMs
    # if model == 'deepseek':
    #     url = 'https://api.deepseek.com/chat/completions'
    #     api_key = ''        
    #     return url, api_key,'deepseek-chat'
    # if model == 'openai':
    #     url = 'https://api.openai.com/v1/responses'
    #     api_key = ''        
    #     return url, api_key, 'gpt-4.1-mini-2025-04-14'

def call_model(system_prompt, prompt, messages=None, output_format=None, tools=None, model='gemini-2.5-flash'):

    url, api_key, model = get_api_info(model)

    data = {
        "model": model,
        "messages": [], # Initialize as empty
        "max_tokens": 8192
    }

    # Add system prompt first
    data['messages'].append({"role": "system", "content": system_prompt})

    if messages is not None:
        data['messages'].extend(messages) # Add previous messages
    
    # Add current user prompt
    data['messages'].append({"role": "user", "content": prompt})
    
    if output_format:
        data['response_format'] = {
            "type": "json_schema",
            "json_schema": {
                "name": "output",
                "schema": output_format  
            }
        }

    if tools:
        data['tools'] = tools

    data_bytes = json.dumps(data).encode('utf-8')
    
    # Retry configuration
    max_retries = 5  # Maximum number of retries
    base_delay = 1  # Initial delay in seconds
    max_delay = 10  # Maximum delay in seconds
    
    for attempt in range(max_retries + 1):  # +1 to include the initial attempt
        req = request.Request(url, data=data_bytes)
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', f'Bearer {api_key}')
        
        try:
            with request.urlopen(req) as resp:
                if resp.status == 200:
                    content = resp.read()
                    output = json.loads(content)
                    print(output)
                    return output['choices'][0]['message']
                else:
                    raise Exception(f"HTTP Error: {resp.status} - {resp.reason}")
                    
        except Exception as e:
            if attempt == max_retries:  # Last attempt failed
                print(f"Error: Final attempt failed after {max_retries} retries: {e}")
                return None
            
            is_http_error = isinstance(e, request.HTTPError)
            is_url_error = isinstance(e, urllib_error.URLError) # Changed to urllib_error.URLError
                
            # Check if it's a 503 error or other retryable error
            if (is_http_error and e.code == 503) or is_url_error:
                # Calculate delay with exponential backoff and jitter
                delay = min(base_delay * (2 ** attempt), max_delay)
                jitter = delay * 0.1 * (0.5 - (0.5 * attempt / max_retries))  # Add some jitter
                sleep_time = delay + jitter
                
                print(f"Attempt {attempt + 1} failed. Retrying in {sleep_time:.2f} seconds... Error: {e}")
                time.sleep(sleep_time)
            else:
                # Non-retryable error
                print(f"Error: {e}")
                return None

lesson_sections = {}
generation_counts = {}

def main_agent(course_plan, lesson_data, chapter_info):
    global lesson_sections
    global generation_counts
    # main agentic loop
    # it is instructed to create a list of requirements of the topic
    # then ask the sub-agent to generate the lesson content
    # it will also ask for a sub-agent to assess the lesson content
    # if the assessor approves the content, the main agent will add it to the course plan
    # if the assessor rejects the content, the main agent will ask the sub-agent to generate a new lesson content
    # the main agent will repeat this process until the course plan is complete
    # the main agent will return the course plan    

    current_sections_str = '\n'.join(lesson_sections.keys())
    system_prompt = f'''
    You are a world-class teacher who is responsible for creating a lesson for a student.
    You will be given a course plan, and a specific lesson topic.
    You will first create a list of requirements of the topic, which may include things like example problems or equations/formulas. 
    Some subjects may call for historical background, for example. In general, please encourage long-form content as much as possible.
    Emphasize this to both the lesson generator and assessor.

    Make sure to tell the assessor to be relatively critical, watching out for content length (longer is preferred, to align with a textbook or blog format).
    We don't want excessively concise/bulleted outputs.

    You have 2 tools:
    1. An agent to generate lesson content (another LLM will generate this content for you)
    2. An agent to assess the lesson content (another LLM will assess the lesson and tell you if it is good)

    Your responsibility will be to instruct these agents to the best of your ability. You can provide them system prompts
    to guide them on how to perform their respective roles. You do not have the ability to directly edit the lesson content. Only the lesson
    generator can edit it and only the assesor can view it. Your only task is to coordinate their roles together. Note that the assessor does not have access to previous feedback, nor can it edit the lesson. ONLY the content generator can modify the lesson content.

    Essentially, this is your full procedure:

    1. Determine the requirements of the lesson topic in context of the full course. Structure this as a set of "sections" that represent individual parts of the lesson. Each section must have a unique numeric ID (e.g., "1", "2", "3") to ensure the sections stay in the correct order.
    2. Based on those requirements, use the generate_lesson_content tool to generate each portion of the lesson.
    3. Request an assessment from the assessor agent by prompting it to assess the lesson based on your requirements.
    4. The assessor will give you an evaluation. 
    5. If the assessor believes the lesson section does not meet your requirements, ask the content generator to re-create the lesson section based on feedback from the assessor.
    6. Repeat this until you have a full, COMPLETE lesson (not just one section) approved by the assessor. PLEASE avoid generating and re-assessing content repeatedly. You shouldn't stay on the same section for more than 3-4 iterations.

    The course the lesson is a part of is called {course_plan['title']}. The description of the course is {course_plan['description']}.
    The chapter the lesson is a part of is called {chapter_info['title']}, which is described as "{chapter_info['description']}."
    
    Here is the information on the lesson you are creating and curating content for: {lesson_data}. Ensure all aspects of the lesson are addressed.    
    The current lesson sections, if any, are: 
    {current_sections_str}
    Only complete the lesson generation after ALL aspects and portions of the lesson are completed.

    This is the number of times each lesson section has been re-written. Please do not exceed 3 re-writes.

    {json.dumps(generation_counts)}

    '''

    tools = [
        {
            "type": "function",
            "function": {
            "name": "generate_lesson_content",
            "description": "Requests another LLM to generate lesson content as per your instructions.",
            "parameters": {
                "type": "object",
                "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The instructions to provide the LLM to generate lesson content.",
                },
                "lesson_section": {
                    "type": "string",
                    "description": "The ID/key of this particular lesson section. This must be a string representation of a number (e.g., '1', '2', '3') to ensure sections are ordered correctly.",
                },                
                },
                "required": ["prompt","lesson_section"],
            },
            }
        },
        {
            "type": "function",
            "function": {
            "name": "assess_lesson_content",
            "description": "Requests another LLM to generate an assessment of the content as per your instructions. It will be provided the full lesson content automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                "system_prompt": {
                    "type": "string",
                    "description": "This describes what criteria and other constraints the LLM should use to provide its evaluation of the lesson content. Remember that the current lesson content will be provided automatically.",
                },                
                },
                "required": ["system_prompt"],
            },
            }
        },
        # {
        #     "type": "function",
        #     "function": {
        #     "name": "complete_lesson_generation",
        #     "description": "If the assessor LLM tells you the all lesson content and sections are good, you will call this function to submit the lesson content. Use this ONLY when ALL lesson sections are finalized to satisfaction.",
        #     "parameters": {
        #         "type": "object",
        #         "properties": {
        #         "complete_reason": {
        #             "type": "string",
        #             "description": "Simply state that the full lesson was approved and tell how many re-evaluations it took.",
        #         },                
        #         },
        #         "required": ["complete_reason"],
        #     },
        #     }
        # },
        
    ]

    # lesson_data = course_plan["chapters"][chapter]['lessons'][lesson]

    completed = False    
    start_prompt = f"Please proceed with the lesson generation."
    messages = []
    while not completed:
        output = call_model(system_prompt,
        prompt = start_prompt,
        messages = messages,
        model='gemini-2.0-flash-lite',
        tools=tools)
        
        if output is None:
            print("Error: call_model returned None in main_agent. Aborting.")
            # Potentially return an error state or raise an exception
            return lesson_sections # Or an empty dict, or handle error appropriately

        messages.append(output)
        tool_result = None # Initialize tool_result

        if 'tool_calls' in output and output['tool_calls'] is not None:
            completed = False
            for tool_call in output['tool_calls']:
                args = json.loads(tool_call['function']['arguments'])
                if tool_call['function']['name'] == 'generate_lesson_content':
                    tool_result = generate_lesson_content(**args)
                elif tool_call['function']['name'] == 'assess_lesson_content':
                    assessment = assess_lesson_content(**args)
                    tool_result = assessment['content'] if assessment and 'content' in assessment else "Assessment error or no content."
                elif tool_call['function']['name'] == 'complete_lesson_generation':
                    completed = True
                    break
                
                if tool_result is not None: # Ensure tool_result was set
                    messages.append({
                        "role": "tool",
                        "content": tool_result,
                        "tool_call_id": tool_call['id']
                    })
                else:
                    # Handle case where tool_result might not have been set (e.g. unknown tool name)
                    print(f"Warning: tool_result not set for tool_call: {tool_call['function']['name']}")
                    messages.append({
                        "role": "tool",
                        "content": "Error: Tool execution failed or tool name not recognized.",
                        "tool_call_id": tool_call['id']
                    })
        else:
            if len(lesson_sections) == 0:
                # Let's double check one more time if the lesson is complete
                # If the lesson is complete, we can break out of the loop
                start_prompt = "Please check if the lesson is complete. If it is, return a message saying 'Lesson complete'. If not, continue building the lesson."
                continue
            else:
                print("No tool calls found in output. Assuming lesson generation is complete.")
                # If no tool calls, we assume the lesson is complete
                # This might be a good place to check if the lesson is actually complete
                # For now, we will just break out of the loop
                completed = True            
    return lesson_sections


def generate_lesson_content(prompt,lesson_section):
    global lesson_sections
    global generation_counts

    lesson_content_schema = {
        "type": "object",
        "properties": {
            "lesson_content": {
                "type": "string",
                "description": "The lesson content"
            },
            # "lesson_section": {
            #     "type": "string",
            #     "description": "The identifier for the lesson section. This will be provided by the user."
            # }
        },
        "required": ["lesson_content"]#, "lesson_section"]
    }
    
    system_prompt = f"""
        You are an expert educator. Generate a portion of a lesson based on the instructions/topic the user provides you.
        In some cases, you may be asked to modify an existing portion of a lesson with some feedback. If that is the case,
        this is the existing section of that lesson: 

        ```
        {lesson_sections.get(lesson_section, '')}
        ```

        Make sure to just output the lesson content, no additional niceties or metadata.
    """
    try:
        model_output = call_model(system_prompt, prompt,model='gemini-2.5-flash')
        if model_output and 'content' in model_output:
            lesson_gen_output = model_output['content']
            lesson_sections[lesson_section] = lesson_gen_output
            generation_counts[lesson_section] = generation_counts.get(lesson_section, 0) + 1
            return f"Sucessfully generated content for section {lesson_section} and saved it, please call the assessor. The total word count of the lesson is {len(' '.join(lesson_sections.values()))}"
        else:
            print(f"Error: call_model did not return expected output for section {lesson_section}")
            return f"Error generating content for section {lesson_section}: No content from model."
    except Exception as e:
        print(e)
        return f"Error generating lesson content: {e}"

def assess_lesson_content(system_prompt):   
    global lesson_sections
    lesson_assessment_schema = {
        "type": "object",
        "properties": {            
            "feedback": {
                "type": "string",
                "description": "The feedback of the lesson content."
            },
            "approved": {
                "type": "boolean",
                "description": "Whether the lesson content is approved."
            }
        },
        "required": ["approved", "feedback"]
    }
    
    model_output = call_model(system_prompt, json.dumps(lesson_sections),model='gemini-2.5-flash')
    if model_output:
        return model_output
    else:
        print("Error: call_model returned None in assess_lesson_content.")
        return {"feedback": "Error during assessment.", "approved": False}
