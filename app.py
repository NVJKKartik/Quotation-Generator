import streamlit as st
import os
from google import genai
from google.genai import types
import tempfile # For handling temporary files
from convert_file_md import convert_md_to_pdf # Added convert_md_to_pdf
from dotenv import load_dotenv
# PIL.Image is not directly used in this refactoring, image bytes are used
# from PIL import Image # Not strictly needed if only using getvalue()

# Initialize the Gemini Client
# This will use the GOOGLE_API_KEY environment variable.
load_dotenv()
client = None
try:
    client = genai.Client()
except Exception as e:
    # Show error in the main app area if sidebar is removed or not primary for this
    # st.error(f"Failed to initialize Gemini Client. Ensure GOOGLE_API_KEY is set and valid. Error: {e}")
    # We'll let the app try to run, and errors will appear if AI features are used without a client.
    pass

# Helper function to add messages to chat history (now stores simple dicts)
def add_message_to_history(role, content, doc_type, image_bytes=None, image_caption=None):
    if f"{doc_type}_messages" not in st.session_state:
        st.session_state[f"{doc_type}_messages"] = []
    message_data = {"role": role, "content": content}
    if image_bytes and image_caption:
        # For display purposes, store image info. For API, image part will be handled separately.
        message_data["image_bytes"] = image_bytes
        message_data["image_caption"] = image_caption
    st.session_state[f"{doc_type}_messages"].append(message_data)

# Helper to prepare `contents` for Gemini API from session state messages
def prepare_gemini_contents(doc_type, current_user_prompt_text=None, image_part_for_prompt=None):
    contents = []
    # System Prompt (Optional - can be the first part of a user message or a dedicated system role)
    # For now, our detailed first-turn prompts serve this role implicitly.

    history = st.session_state.get(f"{doc_type}_messages", [])
    for msg in history:
        role = msg["role"]
        # For API, text content is primary. Image display handled by UI.
        # If an image was part of a specific historical turn for API context (rare for this app), it would need special handling here.
        parts = [types.Part.from_text(text=msg["content"])]
        contents.append(types.Content(role=role, parts=parts))

    # Add the current user prompt if it's not already the last one in history
    # (add_message_to_history usually adds it, so this might be redundant or for specific cases)
    if current_user_prompt_text:
        current_parts = [types.Part.from_text(text=current_user_prompt_text)]
        if image_part_for_prompt: # If the current prompt is tied to an image (e.g., extraction)
            current_parts.insert(0, image_part_for_prompt) # Typically image first, then text
        contents.append(types.Content(role="user", parts=current_parts))
    
    return contents

# Function to handle the chat interface for a given document type (Quotation or Bill)
def run_chat_interface(doc_type_name: str):
    st.header(f"{doc_type_name} Generator Chat")

    if f"{doc_type_name}_messages" not in st.session_state:
        st.session_state[f"{doc_type_name}_messages"] = []
    if f"current_{doc_type_name.lower()}_md" not in st.session_state:
        st.session_state[f"current_{doc_type_name.lower()}_md"] = None
    if f"{doc_type_name}_uploaded_file_info" not in st.session_state:
        st.session_state[f"{doc_type_name}_uploaded_file_info"] = None
    if f"{doc_type_name}_last_uploaded_filename" not in st.session_state:
        st.session_state[f"{doc_type_name}_last_uploaded_filename"] = None

    for message in st.session_state[f"{doc_type_name}_messages"]:
        with st.chat_message(message["role"]):
            if "image_bytes" in message and message["image_bytes"]:
                # Display image if it's part of the message (e.g., user uploaded image confirmation)
                st.image(message["image_bytes"], caption=message.get("image_caption", "Uploaded Image"), use_container_width=True)
            st.markdown(message["content"])

    uploaded_file = st.file_uploader(
        f"Upload a handwritten {doc_type_name} or an existing {doc_type_name} document (optional)",
        type=['jpg', 'jpeg', 'png', 'pdf'],
        key=f"{doc_type_name}_chat_uploader"
    )

    if uploaded_file is not None:
        if st.session_state[f"{doc_type_name}_last_uploaded_filename"] != uploaded_file.name:
            uploaded_file_data = uploaded_file.getvalue()
            st.session_state[f"{doc_type_name}_uploaded_file_info"] = {"name": uploaded_file.name, "type": uploaded_file.type, "data": uploaded_file_data}
            st.session_state[f"{doc_type_name}_last_uploaded_filename"] = uploaded_file.name
            
            user_msg_text = f"Uploaded `{uploaded_file.name}`. How should I process this for a {doc_type_name}? (e.g., 'Extract details', 'Summarize')"
            if uploaded_file.type.startswith("image/"):
                add_message_to_history("user", user_msg_text, doc_type_name, image_bytes=uploaded_file_data, image_caption=f"Uploaded: {uploaded_file.name}")
            else:
                add_message_to_history("user", user_msg_text, doc_type_name)
            st.rerun()

    # Download button for the current document
    if st.session_state[f"current_{doc_type_name.lower()}_md"]:
        st.markdown("---<y_bin_412>Download Current Document---") # Visual separator
        current_md_content = st.session_state[f"current_{doc_type_name.lower()}_md"]
        # Create a temporary MD file to convert
        with tempfile.NamedTemporaryFile(delete=False, suffix=".md", mode="w", encoding="utf-8") as tmp_md_file:
            tmp_md_file.write(current_md_content)
            tmp_md_path = tmp_md_file.name
        
        # Define path for the temporary PDF output
        tmp_pdf_path = tmp_md_path.replace(".md", ".pdf")
        pdf_conversion_success = False
        try:
            pdf_conversion_success = convert_md_to_pdf(tmp_md_path, tmp_pdf_path)
        except Exception as e:
            st.error(f"PDF conversion error for download: {e}")

        if pdf_conversion_success and os.path.exists(tmp_pdf_path):
            with open(tmp_pdf_path, "rb") as pdf_file:
                pdf_bytes = pdf_file.read()
            st.download_button(
                label=f"Download Current {doc_type_name} as PDF",
                data=pdf_bytes,
                file_name=f"{doc_type_name.lower().replace(' ', '_')}_generated.pdf",
                mime="application/pdf",
                key=f"{doc_type_name}_download_pdf_chat"
            )
            # Clean up temporary files
            if os.path.exists(tmp_md_path): os.remove(tmp_md_path)
            if os.path.exists(tmp_pdf_path): os.remove(tmp_pdf_path)
        else:
            if os.path.exists(tmp_md_path): os.remove(tmp_md_path)
            # st.warning(f"Could not prepare PDF for download at this moment.") # Optional warning

    if user_chat_input := st.chat_input(f"Chat about your {doc_type_name}..."):
        add_message_to_history("user", user_chat_input, doc_type_name)
        api_call_needed = True # Flag to determine if we should call Gemini
        gemini_api_contents = []

        # Define uploaded_info and current_doc_md before they are used
        uploaded_info = st.session_state.get(f"{doc_type_name}_uploaded_file_info")
        current_doc_md = st.session_state.get(f"current_{doc_type_name.lower()}_md")
        user_input_lower = user_chat_input.lower() # Still useful for other potential logic, but not for upload triggering
        
        final_prompt_for_api = user_chat_input # Default to raw user input
        image_part_for_current_api_call = None

        if uploaded_info: # If a file was uploaded in the previous interaction and is pending processing
            st.write(f"Debug: Prioritizing processing of previously uploaded file: {uploaded_info.get('name', 'N/A')}")
            raw_data = uploaded_info.get('data')
            mime_type_for_api = uploaded_info.get('type')
            
            if raw_data and mime_type_for_api:
                # Construct Part directly for image/blob data
                image_part_for_current_api_call = types.Part(inline_data=types.Blob(data=raw_data, mime_type=mime_type_for_api))
                # Select the appropriate extraction template based on doc_type_name
                if doc_type_name == "Quotation":
                    final_prompt_for_api = st.session_state.get('quotation_extraction_prompt_template', '').format(doc_type_name=doc_type_name)
                else: # For "Bill" or other types needing extraction
                    final_prompt_for_api = st.session_state.get('bill_extraction_prompt_template', '').format(doc_type_name=doc_type_name)
                # The user_chat_input for this turn is considered a confirmation/go-ahead.
                # The main instruction for LLM is the extraction template.
            else:
                api_call_needed = False
                add_message_to_history("assistant", "Error: Uploaded file data is missing or corrupt.", doc_type_name)
            
            # Clear uploaded file info after this processing attempt
            st.session_state[f"{doc_type_name}_uploaded_file_info"] = None
            st.session_state[f"{doc_type_name}_last_uploaded_filename"] = None

        elif current_doc_md: # No pending upload to process, but there's an existing document
            st.write("Debug: Contextualizing with existing document for modification/query.")
            final_prompt_for_api = f"Here is the current {doc_type_name} document (in Markdown):\n------------------------\n{current_doc_md}\n------------------------\n\nBased on the above document, please address my following request:\n{user_chat_input}"
            
        else: # No pending upload, no current document. Treat as new generation from user_chat_input.
            st.write("Debug: Creating new document from instructions (or general query).")
            # final_prompt_for_api is already user_chat_input (the default), no changes needed here.
        
        # Fallback if prompt ended up empty (should be rare with default to user_chat_input)
        if not final_prompt_for_api.strip():
            api_call_needed = False
            add_message_to_history("assistant", "It seems your request is empty. Please provide some instructions.", doc_type_name)

        if api_call_needed:
            # Prepare conversational history for 'contents'
            gemini_api_contents = []
            system_prompt_text = st.session_state.get('system_prompt', '')

            # Prepend system prompt as the first user message if it exists
            if system_prompt_text.strip():
                gemini_api_contents.append(types.Content(role="user", parts=[types.Part.from_text(text=system_prompt_text)]))

            # Ensure to fetch messages *before* the current user input which is added last
            history_messages = st.session_state.get(f"{doc_type_name}_messages", [])
            
            # The last message in session_state is the current user's input, which will be formatted
            # with final_prompt_for_api and added after the history.
            # So, iterate up to the second to last message for history.
            for msg_data in history_messages[:-1]: 
                api_role = "model" if msg_data["role"] == "assistant" else msg_data["role"]
                if api_role not in ["user", "model"]:
                    st.warning(f"Skipping historical message with invalid role: {msg_data['role']}")
                    continue
                gemini_api_contents.append(types.Content(role=api_role, parts=[types.Part.from_text(text=msg_data["content"])]))
            
            # Add current user prompt with its specific prompt template and potential image
            current_user_parts = [types.Part.from_text(text=final_prompt_for_api)]
            if image_part_for_current_api_call: # This is for extraction
                current_user_parts.insert(0, image_part_for_current_api_call)
            gemini_api_contents.append(types.Content(role="user", parts=current_user_parts))
            
            with st.chat_message("assistant"):
                with st.spinner(f"Thinking..."):
                    try:
                        # print(f"Sending to Gemini Contents: {gemini_api_contents}") # DEBUG
                        response = client.models.generate_content(
                            model='gemini-2.5-flash-preview-04-17', # User updated model
                            contents=gemini_api_contents
                            # Removed generation_config here
                        )
                        ai_response_text = response.text
                        st.markdown(ai_response_text)
                        add_message_to_history("assistant", ai_response_text, doc_type_name)
                        st.session_state[f"current_{doc_type_name.lower()}_md"] = ai_response_text # Update current doc
                    except Exception as e:
                        error_msg = f"Error with Gemini API: {e}"
                        st.error(error_msg)
                        add_message_to_history("assistant", error_msg, doc_type_name)
        st.rerun()

# Define prompt templates (can be loaded from elsewhere or kept here)
# These should be stored in session_state at app start if they are long or to avoid redefinition.
def load_prompt_templates():
    st.session_state['system_prompt'] = """
    You are an AI assistant specialized in creating and processing business documents like quotations and bills.
    Your primary goal is to help the user generate accurate, well-formatted Markdown documents based on their instructions or by extracting information from uploaded files (images or PDFs).
    Follow user instructions meticulously. For quotations and bills, pay close attention to itemized lists, pricing, quantities, totals, and terms and conditions.
    When modifying documents, apply changes accurately to the provided Markdown.
    
    IMPORTANT GUIDELINES:
    1. DO NOT include any comments, notes, or explanations in brackets within the final document. The output should be a clean, professional document ready for PDF conversion.
    2. By default, use "Diagnoedge" as the sender/company name unless the user specifically requests a different sender.
    3. If you encounter Hindi or Devanagari script in the input, convert it to English (Roman script) in your output.
    4. Always format currency values consistently (e.g., ₹500.00 or Rs. 500).
    5. Calculate the necessary values like total, subtotal, GST and fill the columns accordingly.
    6. Leave space for letterhead.
    7. Don't have any heading for the document. It should never start with "##" or any other heading.
    8. Include proper headers, footers, and document structure.
    9. Use Bullet points for the terms and conditions.
    If information is missing for a standard document, you may make reasonable assumptions to create a usable draft and clearly state these assumptions at the beginning of your response, but NOT in the document itself (e.g., "I've assumed a quantity of 1 for items where not specified.").
    
    Avoid using generic placeholders like "[Customer Name]" unless the user specifically asks for a template structure. If details are missing, it's often better to omit the specific sub-field.
    
    Always output your final response as a complete Markdown document for the requested quotation or bill. Do not include conversational pleasantries or extraneous text outside of the Markdown document itself in your final document output, unless specifically part of the document (e.g., a cover letter section if requested).
    
    When extracting from an uploaded file, if the file is an image or PDF of a document, use the provided few-shot examples and instructions to guide your extraction.
    """
    st.session_state['quotation_extraction_prompt_template'] = """
    You are an expert at analyzing images of handwritten documents and converting them into structured Markdown.
    Here is an example of how to process a handwritten quotation:
    EXAMPLE INPUT: An image of a handwritten quotation, typically containing a recipient, sender, an itemized list in a table format with columns like 'Serial No.', 'Item', 'Price', 'GST', 'Final Amount', and a section for terms and conditions.
    EXAMPLE DESIRED OUTPUT (Markdown):

    ```markdown
    <!-- Leave space for letterhead -->





    To:
    The Superintendent
    Govt Ayurved Hospital
    Raipur
    Sub: Supply & Pricing of lab requirements
    Respected Sir,
    We are pleased to inform you best possible rates for the following items.
    | Serial No. | Item                      | Price | GST | Final Amount |
    |------------|---------------------------|-------|-----|--------------|
    | 1          | RA-kit                    | 510   | 0%  | 510          |
    | 2          | CRP-kit                   | 890   | 5%  | 934.5        |
    | 3          | Disposable ESR pipehc     | 800   | 18% | 944          |
    | 4          | Urine Pregnancy test card | 600   | 5%  | 630          |
    | 5          | Hbstg kit                 | 390   | 5%  | 400.5        |
    | 6          | A.S.O.                    | 1150  | 12% | 1288         |
    | 7          | Lancet                    | 85    | 12% | 95.2         |


    Terms and conditions:
    <ul>
    <li>Supply within 15 days after receiving the confirmed order in writing</li>
    <li>Validity of Quotation is one month</li>
    <li>100% Payment in advanced</li>
    </ul>

    Thanks and Regards
    Diagnoedge
    Charoda
    ```
    ---END OF EXAMPLE---
    Now, analyze the following uploaded document (image or PDF), which is expected to be a {doc_type_name}.
    Extract details and structure them clearly in the Markdown format shown in the EXAMPLE DESIRED OUTPUT.
    
    IMPORTANT GUIDELINES based on the example:
    1. DO NOT include any comments, notes, or explanations in brackets within the final document.
    2. Leave space for letterhead (as shown with the HTML comment and blank lines in the example).
    3. The document should NOT start with a Markdown heading (e.g., ##).
    4. By default, use "Diagnoedge" as the sender/company name unless clearly different in the document.
    5. If you encounter Hindi or Devanagari script, convert it to English (Roman script).
    6. Ensure all itemized details, terms, and totals are captured accurately.
    7. For 'Terms and conditions', format them as an HTML unordered list: start with <code>&lt;ul&gt;</code>, end with <code>&lt;/ul&gt;</code>, and wrap each item in <code>&lt;li&gt;...&lt;/li&gt;</code> tags, exactly as shown in the example.
    8. For concluding remarks like 'Thanks and Regards', ensure each part (e.g., name, location) is on its own separate new line, as shown in the example.
    
    The output must be a clean, professional Markdown document, ready for PDF conversion. Output only the Markdown document itself.
    """
    st.session_state['bill_extraction_prompt_template'] = """
    Analyze the uploaded document (image or PDF) of a handwritten {doc_type_name}.
    Extract details and structure them clearly in Markdown format:
    - Document Type (Confirm it is a {doc_type_name})
    - Date, From/Vendor, To/Customer
    - Itemized List (Description, Quantity, Unit Price, Total Price)
    - Subtotal, Taxes, Discounts, Grand Total
    - Terms and conditions.
    
    IMPORTANT GUIDELINES:
    1. DO NOT include any comments, notes, or explanations in brackets within the final document.
    2. Don't have any heading for the document. It should never start with "##" or any other heading.
    3. Leave space for letterhead.
    4. By default, use "Diagnoedge" as the sender/company name unless clearly different in the document.
    5. If you encounter Hindi or Devanagari script, convert it to English (Roman script).
    6. Format currency values consistently (e.g., ₹500.00 or Rs. 500).
    7. Include proper headers and document structure.
    
    The output should be a clean, professional document ready for PDF conversion. Output only the Markdown document.
    """

def main():
    st.set_page_config(layout="wide")
    st.title("AI Document Generator (Chat Mode)")
    load_prompt_templates() # Load templates into session state

    if client is None:
        st.error("Gemini Client failed to initialize. Check GOOGLE_API_KEY.")
        return

    tab_titles = ["Quotation Generator", "Bill Generator"]
    tab_quotation, tab_bill = st.tabs(tab_titles)

    with tab_quotation:
        run_chat_interface("Quotation")

    with tab_bill:
        run_chat_interface("Bill")

if __name__ == "__main__":
    main()
