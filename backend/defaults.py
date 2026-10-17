"""Factory defaults for admin-editable settings. Everything here is overridable from the admin console."""

DISPOSITION_CODES = ["RPC_CONFIRMED", "CPC_CONFIRMED", "CALLBACK_REQUESTED", "FINAL_DENIAL",
                     "FINAL_DENIAL_CLOSING", "HOSTILE", "DECEASED_CASE", "DNC_ESCALATION"]

SCRIPT_KEYS = ["opening", "clarify", "reverify", "confirmed_close", "cpc_close", "callback_close", "denial_close",
               "hostile_close", "deceased_close", "dnc_close"]

DEFAULT_DISPOSITIONS = [
    {"code": "RPC_CONFIRMED", "category": "Right Party Contact", "close": "confirmed_close",
     "description": "The callee explicitly confirms they ARE {{customer_name}} (e.g. 'yes, I am', 'haan, main hi hoon', 'hyan, ami')."},
    {"code": "CPC_CONFIRMED", "category": "Third Party Contact", "close": "cpc_close",
     "description": "Someone else answers (family member / known contact) and confirms {{customer_name}} can be reached on this number, but the customer is not on the line."},
    {"code": "CALLBACK_REQUESTED", "category": "Follow Up", "close": "callback_close",
     "description": "The callee is busy or asks to be called back later."},
    {"code": "FINAL_DENIAL", "category": "Wrong Party", "close": "denial_close",
     "description": "The callee clearly denies being {{customer_name}}, says wrong number, or does not know the customer."},
    {"code": "FINAL_DENIAL_CLOSING", "label": "Final Denial Closing", "category": "Not Verified", "close": "denial_close",
     "description": "Identity could not be established: no clear answer after one clarification, silence, voicemail, no answer, or the call dropped."},
    {"code": "HOSTILE", "category": "Escalation", "close": "hostile_close",
     "description": "The callee is angry, abusive or threatening."},
    {"code": "DECEASED_CASE", "category": "Special Case", "close": "deceased_close",
     "description": "The callee reports that {{customer_name}} has passed away."},
    {"code": "DNC_ESCALATION", "category": "Compliance", "close": "dnc_close",
     "description": "The callee asks not to be called again, or threatens a complaint or legal action."},
]

DEFAULT_VOICE_PROFILES = [
    {"language": "en-IN", "label": "English", "tts_provider": "11labs", "tts_model": "eleven_turbo_v2_5",
     "female_voice_id": "90ipbRoKi4CpHXvKVtl0", "female_voice_name": "Anika — Indian English, customer care",
     "male_voice_id": "pzxut4zZz4GImZNlqQ3H", "male_voice_name": "Raju — Indian English, natural conversational",
     "stt_provider": "deepgram", "stt_model": "nova-3", "stt_language": "en"},
    {"language": "bn-IN", "label": "Bengali", "tts_provider": "11labs", "tts_model": "eleven_v3",
     "female_voice_id": "611e0Wo6wEi3GcpkO5it", "female_voice_name": "Ananya — Kolkata Bengali, polite & firm",
     "male_voice_id": "GuSivqtqi1qfWxEuGhqa", "male_voice_name": "Dipankar — Bengali, natural & calm",
     "stt_provider": "azure", "stt_model": "", "stt_language": "bn-IN"},
    {"language": "hi-IN", "label": "Hindi", "tts_provider": "11labs", "tts_model": "eleven_v3",
     "female_voice_id": "1qEiC6qsybMkmnNdVMbK", "female_voice_name": "Monika Sogam — Hindi, calm & natural",
     "male_voice_id": "zT03pEAEi0VHKciJODfn", "male_voice_name": "Raju — Hindi, clear, natural & warm",
     "stt_provider": "deepgram", "stt_model": "nova-3", "stt_language": "hi"},
]

LEGACY_VOICE_IDS = {"21m00Tcm4TlvDq8ikWAM", "pNInz6obpgDQGcFmaJgB"}

DEFAULT_STATE_RULES = [{"state": "West Bengal", "language": "bn-IN"}]

DEFAULT_EMOTION = (
    "Sound like a warm, caring human — never robotic. Speak naturally with gentle pauses.\n"
    "- Default: warm and empathetic.\n"
    "- If the callee reports a death: slow down, speak softly and offer genuine condolences.\n"
    "- If the callee is hostile: stay calm and apologetic, never argue or raise your tone.\n"
    "- If the callee is friendly: be cheerful and light.\n"
    "- On confirmation: thank them warmly and close. On denial: apologise for the disturbance and close."
)

DEFAULT_SCRIPTS = {
    "en-IN": {
        "opening": "Namaste, I am {{agent_name}} calling from {{bank_name}}. This is a recorded call. Am I speaking with {{customer_name}} ji?",
        "clarify": "Sorry, just to be sure — am I speaking with {{customer_name}} ji?",
        "reverify": "Our records show this number is registered under {{customer_name}} ji. Do you know them?",
        "confirmed_close": "Thank you so much, {{customer_name}} ji. I was calling only to confirm your name. Have a wonderful day!",
        "cpc_close": "Thank you for confirming. Could you please let {{customer_name}} ji know that {{bank_name}} tried to reach them? Have a good day.",
        "callback_close": "Of course, no problem at all. We will call you back at a better time. Thank you!",
        "denial_close": "I'm so sorry for disturbing you. Thank you for your time, and have a good day.",
        "hostile_close": "I sincerely apologise for the inconvenience. I won't take any more of your time. Thank you.",
        "deceased_close": "I am truly sorry for your loss. Please accept our heartfelt condolences. We will update our records. Please take care.",
        "dnc_close": "Understood. I have noted your request and it will be escalated right away. Sorry for the disturbance.",
    },
    "hi-IN": {
        "opening": "नमस्ते, मेरा नाम {{agent_name}} है, यह कॉल {{bank_name}} की ओर से है। यह कॉल रिकॉर्ड की जा रही है। क्या मेरी बात {{customer_name}} जी से हो रही है?",
        "clarify": "माफ़ कीजिए, बस पक्का करना था — क्या मेरी बात {{customer_name}} जी से हो रही है?",
        "reverify": "हमारे रिकॉर्ड में यह नंबर {{customer_name}} जी के नाम पर दर्ज है। क्या आप उन्हें जानते हैं?",
        "confirmed_close": "बहुत-बहुत धन्यवाद, {{customer_name}} जी। आपका नाम कन्फ़र्म करने के लिए ही यह कॉल किया था। आपका दिन शुभ हो!",
        "cpc_close": "पुष्टि करने के लिए धन्यवाद। कृपया {{customer_name}} जी को बता दीजिए कि {{bank_name}} से कॉल आया था। धन्यवाद।",
        "callback_close": "बिल्कुल, कोई बात नहीं। हम आपको बाद में सही समय पर कॉल करेंगे। धन्यवाद!",
        "denial_close": "आपको परेशान करने के लिए माफ़ी चाहते हैं। आपके समय के लिए धन्यवाद।",
        "hostile_close": "असुविधा के लिए हम दिल से माफ़ी चाहते हैं। हम आपका और समय नहीं लेंगे। धन्यवाद।",
        "deceased_close": "यह सुनकर हमें बहुत दुख हुआ। हमारी गहरी संवेदनाएँ आपके साथ हैं। हम अपने रिकॉर्ड अपडेट कर देंगे। अपना ख़याल रखिए।",
        "dnc_close": "जी, आपकी बात नोट कर ली गई है और इसे तुरंत आगे बढ़ाया जाएगा। परेशानी के लिए माफ़ी।",
    },
    "bn-IN": {
        "opening": "নমস্কার, আমার নাম {{agent_name}}, আমি {{bank_name}} থেকে ফোন করছি। এই কলটি রেকর্ড করা হচ্ছে। আমি কি {{customer_name}} জি-র সাথে কথা বলছি?",
        "clarify": "মাফ করবেন, শুধু নিশ্চিত হতে চাইছি — আমি কি {{customer_name}} জি-র সাথে কথা বলছি?",
        "reverify": "আমাদের রেকর্ডে এই নম্বরটি {{customer_name}} জি-র নামে নথিভুক্ত আছে। আপনি কি ওঁকে চেনেন?",
        "confirmed_close": "অনেক ধন্যবাদ, {{customer_name}} জি। আপনার নামটা কনফার্ম করার জন্যই কলটা করছিলাম। আপনার দিনটি ভালো কাটুক!",
        "cpc_close": "নিশ্চিত করার জন্য ধন্যবাদ। অনুগ্রহ করে {{customer_name}} জি-কে জানাবেন যে {{bank_name}} থেকে ফোন এসেছিল। ধন্যবাদ।",
        "callback_close": "অবশ্যই, কোনো সমস্যা নেই। আমরা পরে সুবিধাজনক সময়ে আপনাকে ফোন করব। ধন্যবাদ!",
        "denial_close": "বিরক্ত করার জন্য আমরা দুঃখিত। আপনার সময়ের জন্য ধন্যবাদ।",
        "hostile_close": "অসুবিধার জন্য আমরা আন্তরিকভাবে ক্ষমা চাইছি। আপনার আর সময় নেব না। ধন্যবাদ।",
        "deceased_close": "এটা শুনে আমরা সত্যিই খুব দুঃখিত। আমাদের আন্তরিক সমবেদনা গ্রহণ করুন। আমরা আমাদের রেকর্ড আপডেট করে দেব। ভালো থাকবেন।",
        "dnc_close": "বুঝেছি, আপনার অনুরোধটি নথিভুক্ত করা হয়েছে এবং আমরা এখনই বিষয়টি এগিয়ে নেব। বিরক্ত করার জন্য দুঃখিত।",
    },
}

LEGACY_DISPOSITION_MAP = {"RPI_CONFIRMED": "RPC_CONFIRMED", "WRONG_PARTY": "FINAL_DENIAL",
                          "NO_ANSWER_VOICEMAIL": "FINAL_DENIAL_CLOSING", "FAILED_NUMBER": "FINAL_DENIAL_CLOSING",
                          "Final Denial Closing": "FINAL_DENIAL_CLOSING"}

CALLBACK_PROMISE_MARKERS = ["representative", "प्रतिनिधि", "প্রতিনিধি"]
