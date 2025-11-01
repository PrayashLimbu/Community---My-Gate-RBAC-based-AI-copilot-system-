# api/ai_tools.py
import json
import vertexai
import traceback # Import traceback for better error logging
from vertexai.generative_models import GenerativeModel, Part, FunctionDeclaration, Tool, ToolConfig, Content
from django.conf import settings
from django.utils import timezone
from .models import Visitor, CustomUser, Event

# -----------------------------------------------------------
# 0. Initialize Vertex AI (Do this once)
# -----------------------------------------------------------
try:
    vertexai.init(project=settings.GCP_PROJECT_ID, location=settings.GCP_LOCATION)
except Exception as e:
    print(f"Error initializing Vertex AI: {e}. Check GCP credentials and settings.")

# -----------------------------------------------------------
# 1. DEFINE THE TOOLS (Gemini Format)
# -----------------------------------------------------------

approve_visitor_func = FunctionDeclaration(
    name="approve_visitor",
    description="Approve a pending visitor pass.",
    parameters={
        "type": "object",
        "properties": {
            "visitor_id": {"type": "string", "description": "The unique ID of the visitor to approve."}
        },
        "required": ["visitor_id"],
    },
)

deny_visitor_func = FunctionDeclaration(
    name="deny_visitor",
    description="Deny a pending visitor pass.",
    parameters={
        "type": "object",
        "properties": {
            "visitor_id": {"type": "string", "description": "The unique ID of the visitor to deny."},
            "reason": {"type": "string", "description": "Optional reason for the denial."}
        },
        "required": ["visitor_id"],
    },
)

checkin_visitor_func = FunctionDeclaration(
    name="checkin_visitor",
    description="Check in an approved visitor at the gate. (Guard/Admin only)",
    parameters={
        "type": "object",
        "properties": {
            "visitor_id": {"type": "string", "description": "The unique ID of the visitor to check in."}
        },
        "required": ["visitor_id"],
    },
)

create_visitor_func = FunctionDeclaration(
    name="create_visitor",
    description="Create a new visitor pass for the resident's household.",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "The full name of the visitor."},
            "purpose": {"type": "string", "description": "Optional: The purpose of the visit (e.g., delivery, meeting, guest)."},
            "time_details": {"type": "string", "description": "Optional: Specify the date and/or time (e.g., 'tonight 8pm', 'tomorrow afternoon', 'Nov 5th 10am'). The system will try to parse this."}
            # Add phone later if needed
        },
        "required": ["name"],
    },
)

# Configure the tool mode (AUTO: model decides, ANY: model must call a function, NONE: model won't call)
GEMINI_TOOL_CONFIG = ToolConfig(
    function_calling_config=ToolConfig.FunctionCallingConfig(
        mode=ToolConfig.FunctionCallingConfig.Mode.AUTO
    )
)

# Create the tool with all available functions
GEMINI_TOOL = Tool(
    function_declarations=[
        approve_visitor_func,
        deny_visitor_func,
        checkin_visitor_func,
        create_visitor_func
    ],
)
GEMINI_TOOL_CONFIG = ToolConfig(
    function_calling_config=ToolConfig.FunctionCallingConfig(
        mode=ToolConfig.FunctionCallingConfig.Mode.AUTO
    )
)

# -----------------------------------------------------------
# 2. TOOL EXECUTOR SERVICE (Updated for Gemini)
# -----------------------------------------------------------

class AICopilotService:
    def __init__(self, user: CustomUser):
        self.user = user
        try:
            # Initialize the Gemini model client
            self.model = GenerativeModel(settings.GEMINI_MODEL_NAME)
        except Exception as e:
            print(f"Error initializing GenerativeModel: {e}")
            self.model = None

    # --- Internal Helpers (_log_event, _get_relevant_visitors_context) remain the same ---
    def _log_event(self, type, actor, visitor, payload=None):
        """Helper function to create an audit event."""
        Event.objects.create(
            type=type,
            actor=actor,
            subject_visitor=visitor,
            payload=payload or {}
        )

    def _get_relevant_visitors_context(self):
        """
        Gets a list of visitors the user might want to act on.
        This is the "context" we send to the AI. (No changes needed here)
        """
        context_visitors = []
        if self.user.role == CustomUser.Role.RESIDENT:
            q = Visitor.objects.filter(
                host_household=self.user.household,
                status=Visitor.Status.PENDING
            )
            context_visitors = list(q.order_by('-created_at')[:10]) # Limit context size

        elif self.user.role in [CustomUser.Role.GUARD, CustomUser.Role.ADMIN]:
            q = Visitor.objects.filter(
                status__in=[Visitor.Status.APPROVED, Visitor.Status.PENDING, Visitor.Status.CHECKED_IN]
            )
            context_visitors = list(q.order_by('-created_at')[:20]) # Limit context size

        if not context_visitors:
            return "There are no relevant visitors right now."

        context_str = "Here are the relevant visitors (max 10-20 shown):\n"
        for v in context_visitors:
            context_str += f"- ID {v.id}: {v.name} (Status: {v.status})\n"
        return context_str

    def _build_system_prompt(self):
        """Builds the main prompt for the AI."""
        visitor_context = self._get_relevant_visitors_context()

        prompt = f"""
        You are a helpful assistant for a community management app. The current user is '{self.user.username}', who has the role of '{self.user.role}'.
        Based on the user's request and the visitor list provided, decide if an action (tool call) is necessary using the available functions.
        Only call a function if the user explicitly asks to perform an action on a specific visitor.

        {visitor_context}

        After you call a function and receive the result, formulate a brief, natural language confirmation message for the user based on that result (e.g., "Visitor Ramesh approved." or "Error: Visitor not found.").
        If no function call is needed, just provide a brief, helpful conversational response.
        """
        return prompt


    # --- Secure Tool Implementations (_approve_visitor, _deny_visitor, _checkin_visitor) remain the same ---
    # These contain our actual business logic and security checks.
    # The AI only *requests* these actions; this code *executes* them safely.

    def _approve_visitor(self, visitor_id):
        """Securely approves a visitor. Returns a result message."""
        try:
            visitor = Visitor.objects.get(id=int(visitor_id)) # Convert ID
        except (Visitor.DoesNotExist, ValueError, TypeError):
            return json.dumps({"status": "error", "message": "Visitor not found."})

        if self.user.role not in [CustomUser.Role.RESIDENT, CustomUser.Role.ADMIN]:
             return json.dumps({"status": "error", "message": "Permission denied: Only Residents or Admins can approve."})
        if (self.user.role == CustomUser.Role.RESIDENT and visitor.host_household != self.user.household):
             return json.dumps({"status": "error", "message": "Permission denied: You can only approve visitors for your own household."})
        if visitor.status != Visitor.Status.PENDING:
            return json.dumps({"status": "error", "message": f"Visitor {visitor.name} is already {visitor.status}."})

        visitor.status = Visitor.Status.APPROVED
        visitor.approved_by = self.user
        visitor.approved_at = timezone.now()
        visitor.save()
        self._log_event(Event.EventType.VISITOR_APPROVED, self.user, visitor)
        return json.dumps({"status": "success", "message": f"Visitor {visitor.name} (ID: {visitor.id}) approved."})

    def _deny_visitor(self, visitor_id, reason="Denied by AI Copilot"):
        """Securely denies a visitor. Returns a result message."""
        try:
            visitor = Visitor.objects.get(id=int(visitor_id))
        except (Visitor.DoesNotExist, ValueError, TypeError):
             return json.dumps({"status": "error", "message": "Visitor not found."})

        if self.user.role not in [CustomUser.Role.RESIDENT, CustomUser.Role.ADMIN]:
             return json.dumps({"status": "error", "message": "Permission denied: Only Residents or Admins can deny."})
        if (self.user.role == CustomUser.Role.RESIDENT and visitor.host_household != self.user.household):
             return json.dumps({"status": "error", "message": "Permission denied: You can only deny visitors for your own household."})
        if visitor.status != Visitor.Status.PENDING:
            return json.dumps({"status": "error", "message": f"Visitor {visitor.name} is already {visitor.status}."})

        visitor.status = Visitor.Status.DENIED
        visitor.save()
        self._log_event(Event.EventType.VISITOR_DENIED, self.user, visitor, {'reason': reason})
        return json.dumps({"status": "success", "message": f"Visitor {visitor.name} (ID: {visitor.id}) denied."})

    def _checkin_visitor(self, visitor_id):
        """Securely checks in a visitor. Returns a result message."""
        try:
            visitor = Visitor.objects.get(id=int(visitor_id))
        except (Visitor.DoesNotExist, ValueError, TypeError):
             return json.dumps({"status": "error", "message": "Visitor not found."})

        if self.user.role not in [CustomUser.Role.GUARD, CustomUser.Role.ADMIN]:
             return json.dumps({"status": "error", "message": "Permission denied: Only Guards or Admins can check in."})
        if visitor.status != Visitor.Status.APPROVED:
            return json.dumps({"status": "error", "message": f"Visitor {visitor.name} must be APPROVED to check in (current status: {visitor.status})."})

        visitor.status = Visitor.Status.CHECKED_IN
        visitor.checked_in_at = timezone.now()
        visitor.save()
        self._log_event(Event.EventType.VISITOR_CHECKIN, self.user, visitor)
        return json.dumps({"status": "success", "message": f"Visitor {visitor.name} (ID: {visitor.id}) checked in."})
    
    def _create_visitor(self, name, purpose=None, time_details=None):
        """Securely creates a visitor for the logged-in resident."""
        if not name:
            return json.dumps({"status": "error", "message": "Visitor name is required."})

        # *** CRITICAL SECURITY CHECK ***
        if self.user.role != CustomUser.Role.RESIDENT:
            return json.dumps({"status": "error", "message": "Permission Denied: Only residents can create visitors."})
        if not self.user.household:
            return json.dumps({"status": "error", "message": "Cannot create visitor: You are not associated with a household."})

        # --- Basic Time Parsing (Needs Improvement for Production) ---
        scheduled_dt = None
        time_parse_message = ""
        if time_details:
            # VERY basic parsing attempt - replace with a proper library like dateutil or pendulum
            # This is just an example and highly unreliable
            from datetime import datetime, timedelta
            now = timezone.now()
            time_details_lower = time_details.lower()
            try:
                if "tonight" in time_details_lower:
                    # Try to find hour/minute like '8pm' or '7:30 am'
                    # Placeholder logic - extremely basic
                    scheduled_dt = now.replace(hour=20, minute=0, second=0, microsecond=0) # Assume 8 PM
                    time_parse_message = f" (Scheduled for approx. {scheduled_dt.strftime('%I:%M %p')})"
                elif "tomorrow" in time_details_lower:
                    scheduled_dt = (now + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0) # Assume 2 PM tomorrow
                    time_parse_message = f" (Scheduled for approx. tomorrow {scheduled_dt.strftime('%I:%M %p')})"
                # Add more parsing logic here...
                else:
                    # Attempt generic parsing (HIGHLY likely to fail often)
                    # scheduled_dt = parse(time_details) # Using a hypothetical parse function
                    time_parse_message = " (Could not precisely determine schedule)"

            except Exception as e:
                print(f"Basic time parsing failed for '{time_details}': {e}")
                time_parse_message = " (Could not determine schedule from text)"


        # --- Create Visitor ---
        try:
            visitor = Visitor.objects.create(
                name=name,
                purpose=purpose or "Guest",
                host_household=self.user.household,
                status=Visitor.Status.PENDING,
                scheduled_time=scheduled_dt # May be None
            )
            # Log event
            self._log_event(Event.EventType.VISITOR_CREATED, self.user, visitor)
            return json.dumps({
                "status": "success",
                "message": f"Visitor '{visitor.name}' created with ID {visitor.id}{time_parse_message}."
            })
        except Exception as e:
            print(f"Error creating visitor in DB: {e}")
            return json.dumps({"status": "error", "message": f"Database error creating visitor: {e}"})


# --- NEW METHOD: _list_my_visitors ---
    def _list_my_visitors(self):
        """Lists visitors for the logged-in resident's household."""
        # *** CRITICAL SECURITY CHECK ***
        if self.user.role != CustomUser.Role.RESIDENT:
            return json.dumps({"status": "error", "message": "Permission Denied: Only residents can list their visitors."})
        if not self.user.household:
            return json.dumps({"status": "error", "message": "Cannot list visitors: You are not associated with a household."})

        visitors = Visitor.objects.filter(host_household=self.user.household).order_by('-created_at')[:20] # Limit results

        if not visitors.exists():
            return json.dumps({"status": "success", "visitor_list_text": "You have no visitors registered."})

        visitor_list_str = "Here are your recent visitors:\n"
        for v in visitors:
            time_str = f" @ {v.scheduled_time.strftime('%b %d, %I:%M %p')}" if v.scheduled_time else ""
            visitor_list_str += f"- ID {v.id}: {v.name} ({v.status}){time_str}\n"

        return json.dumps({"status": "success", "visitor_list_text": visitor_list_str})
        # -----------------------------------------------------------
    # 4. MAIN PUBLIC METHOD (Updated for Gemini)
    # -----------------------------------------------------------

    def process_message(self, history: list):
        if not self.model:
            return "Error: AI Model not initialized. Check Vertex AI setup."

        system_prompt = self._build_system_prompt()

    # --- Convert frontend history to Gemini Content objects ---
        gemini_history = []
        for msg in history:
            role = msg.get('role', 'user') # 'user' or 'model'
            text = msg.get('text', '')
            # Ensure we only add valid text parts
            if text:
                try:
                    # Explicitly create Content object for each history item
                    gemini_history.append(Content(role=role, parts=[Part.from_text(text)]))
                except Exception as e:
                    print(f"Warning: Skipping invalid history message part: {e} - {msg}")
            else:
                print(f"Warning: Skipping history message with empty text: {msg}")

        # --- Construct the final list for the API call ---
        # Ensure every item is definitely a Content object
        final_contents = [
            # Start with system instructions (as a 'user' turn for some models)
            Content(role="user", parts=[Part.from_text(system_prompt)]),
            # Add a priming 'model' turn
            Content(role="model", parts=[Part.from_text("Okay, I'm ready. How can I assist with visitors?")]),
            # Add the validated chat history
            *gemini_history
        ]

        # --- Debugging: Check types before sending ---
        print("\n--- Sending to Gemini ---")
        for i, item in enumerate(final_contents):
            print(f"Item {i}: Type={type(item)}, Role={getattr(item, 'role', 'N/A')}")
            if not isinstance(item, Content):
                print(f"ERROR: Item {i} is NOT a Content object!")
        print("-------------------------\n")
        # --- End Debugging ---
        
        try:
            # --- 1. Call Gemini ---
            response = self.model.generate_content(
                final_contents,
                tools=[GEMINI_TOOL],
                tool_config=GEMINI_TOOL_CONFIG,
            )

            # --- 2. Check for Function Calls Safely ---
            candidate = response.candidates[0]
            # Find all parts that are function calls
            function_calls = [
                part.function_call for part in candidate.content.parts
                if hasattr(part, 'function_call') and part.function_call is not None and getattr(part.function_call, 'name', None)
            ]
            if function_calls: # If the list is not empty (AI wants to use tools)
                print(f"Gemini wants to call {len(function_calls)} tool(s).") # Debugging
                
                # --- 3. Execute ALL function calls ---
                function_responses_for_gemini = []
                
                for function_call in function_calls:
                    function_name = function_call.name
                    function_args = dict(function_call.args)
                    print(f"Executing: {function_name} with args: {function_args}") # Debugging

                    # Execute securely
                    if function_name == "approve_visitor":
                        api_response_content_str = self._approve_visitor(visitor_id=function_args.get("visitor_id"))
                    elif function_name == "deny_visitor":
                         api_response_content_str = self._deny_visitor(visitor_id=function_args.get("visitor_id"), reason=function_args.get("reason"))
                    elif function_name == "checkin_visitor":
                         api_response_content_str = self._checkin_visitor(visitor_id=function_args.get("visitor_id"))
                    elif function_name == "create_visitor":
                         api_response_content_str = self._create_visitor(name=function_args.get("name"), purpose=function_args.get("purpose"), time_details=function_args.get("time_details"))
                    elif function_name == "list_my_visitors":
                         api_response_content_str = self._list_my_visitors()
                    else:
                        api_response_content_str = json.dumps({"status":"error", "message": f"Unknown function requested: {function_name}"})
                    
                    print(f"Function result: {api_response_content_str}") # Debugging

                    # Parse result and append to responses for Gemini
                    try: api_response_dict = json.loads(api_response_content_str)
                    except json.JSONDecodeError: api_response_dict = {"status": "error", "message": "Internal function returned invalid format."}
                    
                    function_responses_for_gemini.append(
                        Part.from_function_response(name=function_name, response=api_response_dict)
                    )
                
                # --- 4. Send ALL Function Results back to Gemini for a final summary ---
                print(f"Sending back {len(function_responses_for_gemini)} function results.") # Debugging

                function_response_content = Content(role="function", parts=function_responses_for_gemini)

                # --- Construct the history for the final call WITH VALIDATION ---
                history_for_final_call = []
                # Add original history items (already validated as Content)
                history_for_final_call.extend(final_contents)

                # Validate and add AI's previous turn (containing function calls)
                ai_previous_turn = candidate.content
                if isinstance(ai_previous_turn, Content):
                    history_for_final_call.append(ai_previous_turn)
                    print("Added AI's function call turn to final history.") # Debug
                else:
                    print(f"ERROR: AI's previous turn was not a Content object! Type: {type(ai_previous_turn)}") # Debug
                    # Decide how to handle this - skip this turn? Return error?
                    # For now, let's try proceeding without it, might lose context.
                    # return "Sorry, encountered an unexpected format from the AI after function call."

                # Add our function execution results (already validated as Content)
                history_for_final_call.append(function_response_content)
                print("Added function response turn to final history.") # Debug

                # --- Debugging: Check final list types ---
                print("\n--- Sending FINAL HISTORY to Gemini ---")
                for i, item in enumerate(history_for_final_call):
                    print(f"Item {i}: Type={type(item)}, Role={getattr(item, 'role', 'N/A')}")
                    if not isinstance(item, Content):
                       print(f"CRITICAL ERROR: Item {i} in final history is NOT Content!")
                print("-------------------------------------\n")
                # --- End Debugging ---

                # Make the call to get the final natural language response
                response = self.model.generate_content(
                    history_for_final_call,
                    # tools=[GEMINI_TOOL], # Tools not needed for summary
                    # tool_config=GEMINI_TOOL_CONFIG, # Config not needed for summary
                )
                
                # --- 5. Return Gemini's final natural language response ---
                if response.candidates and response.candidates[0].content.parts and response.candidates[0].content.parts[0].text:
                     return response.candidates[0].content.parts[0].text
                else:
                     return "Actions completed, but AI provided no final summary."

            elif candidate.content.parts and candidate.content.parts[0].text:
                # --- 6. No function call, just return the initial text response ---
                print("Gemini returned text response directly.") # Debugging
                return candidate.content.parts[0].text
            else:
                 # Handle cases where the first response wasn't text or function call
                 print("Warning: Gemini response structure unexpected.") # Debugging
                 return "I received a response, but couldn't understand its format."

        except Exception as e:
            print(f"Error during AI processing: {e}")
            traceback.print_exc()
            return f"Sorry, there was an error processing your request with the AI model."