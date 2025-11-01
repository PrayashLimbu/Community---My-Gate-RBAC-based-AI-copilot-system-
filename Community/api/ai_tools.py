# Community/api/ai_tools.py
import json
import vertexai
import traceback
from vertexai.generative_models import GenerativeModel, Part, FunctionDeclaration, Tool, ToolConfig, Content
from django.conf import settings
from django.utils import timezone
from .models import Visitor, CustomUser, Event, FCMDevice
# from firebase_admin import messaging # (Keep if using FCM)
from datetime import datetime, timedelta # For basic time parsing

# --- Initialize Vertex AI ---
try:
    vertexai.init(project=settings.GCP_PROJECT_ID, location=settings.GCP_LOCATION)
except Exception as e:
    print(f"Error initializing Vertex AI: {e}")

# -----------------------------------------------------------
# 1. DEFINE THE TOOLS (Gemini Format)
# -----------------------------------------------------------

# --- Tool 1: Create Visitor (UPGRADED) ---
create_visitor_func = FunctionDeclaration(
    name="create_visitor",
    description="Create one or more new visitor passes for the resident's household.",
    parameters={
        "type": "object",
        "properties": {
            # UPGRADED to accept a list of names
            "names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "A list of one or more visitor names (e.g., ['John Doe', 'Jane Smith'])."
            },
            "purpose": {"type": "string", "description": "Optional: The purpose of the visit (e.g., dinner party, delivery)."},
            "time_details": {"type": "string", "description": "Optional: Date/time for the visit (e.g., 'tonight 8pm', 'tomorrow')."}
        },
        "required": ["names"],
    },
)

# --- Tool 2: List Visitors (UPGRADED) ---
list_my_visitors_func = FunctionDeclaration(
    name="list_my_visitors",
    description="List visitors associated with the resident's household, optionally filtering by status.",
    parameters={
        "type": "object",
        "properties": {
            # NEW parameter
            "status": {
                "type": "string",
                "enum": ["PENDING", "APPROVED", "CHECKED_IN", "CHECKED_OUT", "DENIED", "ALL"],
                "description": "The status to filter by. Default is 'ALL'."
            }
        },
    },
)

# --- Tool 3 & 4 (Unchanged) ---
approve_visitor_func = FunctionDeclaration(
    name="approve_visitor",
    description="Approve a pending visitor pass using its unique ID.",
    parameters={ "type": "object", "properties": { "visitor_id": {"type": "string"} }, "required": ["visitor_id"] },
)
deny_visitor_func = FunctionDeclaration(
    name="deny_visitor",
    description="Deny a pending visitor pass using its unique ID.",
    parameters={ "type": "object", "properties": { "visitor_id": {"type": "string"}, "reason": {"type": "string"} }, "required": ["visitor_id"] },
)
checkin_visitor_func = FunctionDeclaration(
    name="checkin_visitor",
    description="Check in an approved visitor at the gate. (Guard/Admin only)",
    parameters={ "type": "object", "properties": { "visitor_id": {"type": "string"} }, "required": ["visitor_id"] },
)

# --- Update the Tool object ---
GEMINI_TOOL = Tool(
    function_declarations=[
        create_visitor_func,   # Upgraded
        list_my_visitors_func, # Upgraded
        approve_visitor_func,
        deny_visitor_func,
        checkin_visitor_func,
    ],
)
GEMINI_TOOL_CONFIG = ToolConfig(
    function_calling_config=ToolConfig.FunctionCallingConfig(
        mode=ToolConfig.FunctionCallingConfig.Mode.AUTO
    )
)

# -----------------------------------------------------------
# 2. TOOL EXECUTOR SERVICE (Updated Methods)
# -----------------------------------------------------------

class AICopilotService:
    def __init__(self, user: CustomUser):
        self.user = user
        try:
            self.model = GenerativeModel(settings.GEMINI_MODEL_NAME)
        except Exception as e:
            print(f"Error initializing GenerativeModel: {e}")
            self.model = None

    def _log_event(self, type, actor, visitor, payload=None):
        Event.objects.create(type=type, actor=actor, subject_visitor=visitor, payload=payload or {})

    def _send_fcm_to_user(self, user, title, body, data=None):
        # (Your FCM sending logic here... if you re-add it)
        pass 

    def _get_relevant_visitors_context(self):
        # ... (This function remains the same as before) ...
        context_visitors = []
        if self.user.role == CustomUser.Role.RESIDENT:
            q = Visitor.objects.filter(host_household=self.user.household, status=Visitor.Status.PENDING)
            context_visitors = list(q.order_by('-created_at')[:10])
        elif self.user.role in [CustomUser.Role.GUARD, CustomUser.Role.ADMIN]:
            q = Visitor.objects.filter(status__in=[Visitor.Status.APPROVED, Visitor.Status.PENDING, Visitor.Status.CHECKED_IN])
            context_visitors = list(q.order_by('-created_at')[:20])
        if not context_visitors: return "There are no relevant visitors right now."
        context_str = "Here are the relevant visitors (max 10-20 shown):\n"
        for v in context_visitors:
            context_str += f"- ID {v.id}: {v.name} (Status: {v.status})\n"
        return context_str

    # --- UPDATED System Prompt ---
    def _build_system_prompt(self):
        visitor_context = self._get_relevant_visitors_context()
        prompt = f"""
        You are a helpful assistant for a community management app. The user is '{self.user.username}', who has the role of '{self.user.role}'.
        Based on the user's request and the visitor list, decide which action(s) to call.
        - You can create *multiple* visitor passes at once (e.g., for a family).
        - You can list visitors by status (pending, approved, etc.).
        - You can combine actions (e.g., create a visitor and then approve them if the user asks).
        - Always use the visitor ID for approving or denying.
        - If a visitor name is ambiguous (e.g., 'approve Ramesh' when there are two), ask for the ID.

        {visitor_context}

        After you call function(s) and get the result, formulate a single, concise, natural language confirmation for the user.
        If no function call is needed, just provide a brief, helpful conversational response.
        """
        return prompt

    # --- (HELPER) Basic Time Parser (Unchanged) ---
    def _parse_time_details(self, time_details):
        if not time_details:
            return None, ""
        
        scheduled_dt = None
        time_parse_message = ""
        now = timezone.now()
        time_details_lower = time_details.lower()
        
        try:
            if "tonight" in time_details_lower:
                hour = 20 # Default 8 PM
                if "7" in time_details_lower: hour = 19
                if "8" in time_details_lower: hour = 20
                if "9" in time_details_lower: hour = 21
                scheduled_dt = now.replace(hour=hour, minute=0, second=0, microsecond=0)
                time_parse_message = f" (Scheduled for approx. tonight at {scheduled_dt.strftime('%I:%M %p')})"
            elif "tomorrow" in time_details_lower:
                hour = 14 # Default 2 PM
                if "am" in time_details_lower: hour = 10 # Default 10 AM
                if "pm" in time_details_lower: hour = 14
                if "2" in time_details_lower: hour = 14
                if "3" in time_details_lower: hour = 15
                scheduled_dt = (now + timedelta(days=1)).replace(hour=hour, minute=0, second=0, microsecond=0)
                time_parse_message = f" (Scheduled for approx. tomorrow at {scheduled_dt.strftime('%I:%M %p')})"
            else:
                time_parse_message = " (Could not precisely determine schedule)"
        except Exception as e:
            print(f"Basic time parsing failed: {e}")
            time_parse_message = " (Could not determine schedule from text)"
            
        return scheduled_dt, time_parse_message

    # --- UPDATED create_visitor Method ---
    def _create_visitor(self, names, purpose=None, time_details=None):
        if not names or not isinstance(names, list) or len(names) == 0:
             return json.dumps({"status": "error", "message": "Visitor name list is required."})
        if self.user.role != CustomUser.Role.RESIDENT:
            return json.dumps({"status": "error", "message": "Permission Denied: Only residents can create visitors."})
        if not self.user.household:
             return json.dumps({"status": "error", "message": "Cannot create visitor: You are not associated with a household."})

        scheduled_dt, time_parse_message = self._parse_time_details(time_details)
        
        created_visitors = []
        try:
            for name in names:
                if not name: continue # Skip empty names in list
                visitor = Visitor.objects.create(
                    name=name,
                    purpose=purpose or "Guest",
                    host_household=self.user.household,
                    status=Visitor.Status.PENDING,
                    scheduled_time=scheduled_dt
                )
                self._log_event(Event.EventType.VISITOR_CREATED, self.user, visitor)
                created_visitors.append(f"'{visitor.name}' (ID {visitor.id})")
            
            if not created_visitors:
                return json.dumps({"status": "error", "message": "No valid visitor names were provided."})

            return json.dumps({
                "status": "success",
                "message": f"Successfully created {len(created_visitors)} visitor(s): {', '.join(created_visitors)}{time_parse_message}."
            })
        except Exception as e:
            print(f"Error creating visitor in DB: {e}")
            return json.dumps({"status": "error", "message": f"Database error creating visitors: {e}"})

    # --- UPDATED list_my_visitors Method ---
    def _list_my_visitors(self, status=None):
        if self.user.role != CustomUser.Role.RESIDENT:
            return json.dumps({"status": "error", "message": "Permission Denied: Only residents can list their visitors."})
        if not self.user.household:
             return json.dumps({"status": "error", "message": "Cannot list visitors: You are not associated with a household."})

        # Base query
        visitor_query = Visitor.objects.filter(host_household=self.user.household)

        # Apply status filter if provided and valid
        valid_statuses = ["PENDING", "APPROVED", "CHECKED_IN", "CHECKED_OUT", "DENIED"]
        if status and status in valid_statuses:
            visitor_query = visitor_query.filter(status=status)
        
        visitors = visitor_query.order_by('-created_at')[:20] # Limit results

        if not visitors.exists():
            filter_text = f" with status '{status}'" if status and status != 'ALL' else ""
            return json.dumps({"status": "success", "visitor_list_text": f"You have no visitors{filter_text}."})

        visitor_list_str = "Here are your recent visitors:\n"
        for v in visitors:
            time_str = f" @ {v.scheduled_time.strftime('%b %d, %I:%M %p')}" if v.scheduled_time else ""
            visitor_list_str += f"- ID {v.id}: {v.name} ({v.status}){time_str}\n"

        # Return the list as a string payload
        return json.dumps({"status": "success", "visitor_list_text": visitor_list_str})
        
    # --- (approve, deny, checkin methods remain the same) ---
    def _approve_visitor(self, visitor_id):
        try: visitor = Visitor.objects.get(id=int(visitor_id))
        except (Visitor.DoesNotExist, ValueError, TypeError): return json.dumps({"status": "error", "message": "Visitor not found."})
        if self.user.role not in [CustomUser.Role.RESIDENT, CustomUser.Role.ADMIN]: return json.dumps({"status": "error", "message": "Permission denied."})
        if (self.user.role == CustomUser.Role.RESIDENT and visitor.host_household != self.user.household): return json.dumps({"status": "error", "message": "Permission denied: Not your visitor."})
        if visitor.status != Visitor.Status.PENDING: return json.dumps({"status": "error", "message": f"Visitor {visitor.name} is already {visitor.status}."})
        visitor.status = Visitor.Status.APPROVED
        visitor.approved_by = self.user
        visitor.approved_at = timezone.now()
        visitor.save()
        self._log_event(Event.EventType.VISITOR_APPROVED, self.user, visitor)
        return json.dumps({"status": "success", "message": f"Visitor {visitor.name} (ID: {visitor.id}) approved."})

    def _deny_visitor(self, visitor_id, reason="Denied by AI Copilot"):
        try: visitor = Visitor.objects.get(id=int(visitor_id))
        except (Visitor.DoesNotExist, ValueError, TypeError): return json.dumps({"status": "error", "message": "Visitor not found."})
        if self.user.role not in [CustomUser.Role.RESIDENT, CustomUser.Role.ADMIN]: return json.dumps({"status": "error", "message": "Permission denied."})
        if (self.user.role == CustomUser.Role.RESIDENT and visitor.host_household != self.user.household): return json.dumps({"status": "error", "message": "Permission denied: Not your visitor."})
        if visitor.status != Visitor.Status.PENDING: return json.dumps({"status": "error", "message": f"Visitor {visitor.name} is already {visitor.status}."})
        visitor.status = Visitor.Status.DENIED
        visitor.save()
        self._log_event(Event.EventType.VISITOR_DENIED, self.user, visitor, {'reason': reason})
        return json.dumps({"status": "success", "message": f"Visitor {visitor.name} (ID: {visitor.id}) denied."})

    def _checkin_visitor(self, visitor_id):
        try: visitor = Visitor.objects.get(id=int(visitor_id))
        except (Visitor.DoesNotExist, ValueError, TypeError): return json.dumps({"status": "error", "message": "Visitor not found."})
        if self.user.role not in [CustomUser.Role.GUARD, CustomUser.Role.ADMIN]: return json.dumps({"status": "error", "message": "Permission denied."})
        if visitor.status != Visitor.Status.APPROVED: return json.dumps({"status": "error", "message": f"Visitor {visitor.name} must be APPROVED to check in."})
        visitor.status = Visitor.Status.CHECKED_IN
        visitor.checked_in_at = timezone.now()
        visitor.checked_in_by = self.user
        visitor.save()
        self._log_event(Event.EventType.VISITOR_CHECKIN, self.user, visitor)
        return json.dumps({"status": "success", "message": f"Visitor {visitor.name} (ID: {visitor.id}) checked in."})


    # --- UPDATED process_message Method ---
    def process_message(self, history: list):
        if not self.model: return "Error: AI Model not initialized."
        
        system_prompt = self._build_system_prompt()
        gemini_history = []
        for msg in history:
            role = msg.get('role', 'user')
            text = msg.get('text', '')
            if text:
                 try: gemini_history.append(Content(role=role, parts=[Part.from_text(text)]))
                 except Exception as e: print(f"Warning: Skipping invalid history message: {e}")
        
        final_contents = [
            Content(role="user", parts=[Part.from_text(system_prompt)]),
            Content(role="model", parts=[Part.from_text("Okay, I'm ready. How can I assist with visitors?")]),
            *gemini_history
        ]

        try:
            # --- 1. Call Gemini ---
            response = self.model.generate_content(final_contents, tools=[GEMINI_TOOL])
            candidate = response.candidates[0]
            
            # --- 2. Check for Function Calls Safely ---
            function_calls = [
                part.function_call for part in candidate.content.parts
                if hasattr(part, 'function_call') and part.function_call is not None and getattr(part.function_call, 'name', None)
            ]

            if function_calls:
                print(f"Gemini wants to call {len(function_calls)} tool(s).")
                function_responses_for_gemini = []
                
                # --- 3. Execute ALL function calls ---
                for function_call in function_calls:
                    function_name = function_call.name
                    function_args = dict(function_call.args)
                    print(f"Executing: {function_name} with args: {function_args}")

                    api_response_content_str = "" # Default
                    if function_name == "create_visitor":
                         api_response_content_str = self._create_visitor(
                             names=function_args.get("names"), # Pass list
                             purpose=function_args.get("purpose"),
                             time_details=function_args.get("time_details")
                         )
                    elif function_name == "list_my_visitors":
                         api_response_content_str = self._list_my_visitors(
                             status=function_args.get("status") # Pass status
                         )
                    elif function_name == "approve_visitor":
                        api_response_content_str = self._approve_visitor(visitor_id=function_args.get("visitor_id"))
                    elif function_name == "deny_visitor":
                         api_response_content_str = self._deny_visitor(visitor_id=function_args.get("visitor_id"), reason=function_args.get("reason"))
                    elif function_name == "checkin_visitor":
                         api_response_content_str = self._checkin_visitor(visitor_id=function_args.get("visitor_id"))
                    else:
                        api_response_content_str = json.dumps({"status":"error", "message": f"Unknown function requested: {function_name}"})
                    
                    print(f"Function result: {api_response_content_str}")

                    try: api_response_dict = json.loads(api_response_content_str)
                    except json.JSONDecodeError: api_response_dict = {"status": "error", "message": "Internal function returned invalid format."}
                    
                    function_responses_for_gemini.append(
                        Part.from_function_response(name=function_name, response=api_response_dict)
                    )
                
                # --- 4. Send ALL Function Results back to Gemini for a final summary ---
                function_response_content = Content(role="function", parts=function_responses_for_gemini)
                history_for_final_call = [*final_contents, candidate.content, function_response_content]

                response = self.model.generate_content(history_for_final_call) # No tools needed here

                # --- 5. Return Gemini's final natural language response ---
                if response.candidates and response.candidates[0].content.parts and response.candidates[0].content.parts[0].text:
                     return response.candidates[0].content.parts[0].text
                else:
                     # If Gemini returns no text, create a default summary
                     success_messages = [json.loads(p.function_response.response['content']).get('message', '') 
                                         for p in function_responses_for_gemini 
                                         if json.loads(p.function_response.response['content']).get('status') == 'success']
                     if success_messages:
                         return "Done. " + " ".join(success_messages)
                     return "Actions completed, but AI provided no final summary."

            elif candidate.content.parts and candidate.content.parts[0].text:
                # --- 6. No function call, just return the initial text response ---
                return candidate.content.parts[0].text
            else:
                 return "I received a response, but couldn't understand its format."

        except Exception as e:
            print(f"Error during AI processing: {e}")
            traceback.print_exc()
            return f"Sorry, there was an error processing your request with the AI model."