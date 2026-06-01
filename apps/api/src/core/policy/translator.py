import re
from typing import Dict, Any, Optional

class CedarPolicyTranslator:
    """
    A robust Natural Language to Cedar Policy translator.
    Translates standard natural language policies into mathematically valid Cedar AST strings
    that are fully compatible with the AgentShield Cedar AST parser.
    """

    @staticmethod
    def translate(natural_language: str) -> Dict[str, Any]:
        text = natural_language.lower().strip()
        
        # Default policy structure
        policy_str = ""
        explanation = ""
        success = False
        
        # 1. Pattern: Forbid specific tool under all conditions
        # E.g., "Block agents from using issue_refund" or "Forbid execute_sql"
        block_tool_match = re.search(
            r"(?:block|forbid|stop|prevent|deny)\s+(?:agents\s+from\s+using\s+|the\s+tool\s+|tool\s+)?([a-zA-Z0-9_]+)\s*$", 
            text
        )
        if block_tool_match:
            tool_name = block_tool_match.group(1)
            policy_str = f"""forbid(
    principal,
    action,
    resource
) when {{
    context.tool_name == "{tool_name}"
}};"""
            explanation = f"Explicitly blocks all executions of the '{tool_name}' tool."
            success = True

        # 2. Pattern: Forbid specific tool when numeric attribute exceeds value
        # E.g., "Block tool issue_refund when amount is greater than 500" or "Forbid issue_refund if amount > 500"
        elif any(x in text for x in ["greater", "more", ">", "above", "exceeds"]):
            # Extract tool and attribute details
            # E.g. block tool issue_refund when amount > 500
            match = re.search(
                r"(?:block|forbid|stop|prevent|deny)\s+(?:the\s+tool\s+|tool\s+)?([a-zA-Z0-9_]+)\s+(?:when|if|where)\s+(?:context\.)?([a-zA-Z0-9_]+)\s*(?:is\s+)?(?:greater\s+than|more\s+than|above|exceeds|>)\s*(?:than\s+)?(?:\$)?([0-9]+(?:\.[0-9]+)?)",
                text
            )
            if match:
                tool_name = match.group(1)
                attr = match.group(2)
                value = match.group(3)
                policy_str = f"""forbid(
    principal,
    action,
    resource
) when {{
    context.tool_name == "{tool_name}" && context.{attr} > {value}
}};"""
                explanation = f"Prevents agent from calling '{tool_name}' if the parameter '{attr}' is greater than {value}."
                success = True

        # 3. Pattern: Forbid specific tool when numeric attribute is less than value
        # E.g., "Block issue_refund when amount is less than 10" or "Forbid refund if amount < 10"
        elif any(x in text for x in ["less", "below", "<", "under"]):
            match = re.search(
                r"(?:block|forbid|stop|prevent|deny)\s+(?:the\s+tool\s+|tool\s+)?([a-zA-Z0-9_]+)\s+(?:when|if|where)\s+(?:context\.)?([a-zA-Z0-9_]+)\s*(?:is\s+)?(?:less\s+than|below|under|<)\s*(?:than\s+)?(?:\$)?([0-9]+(?:\.[0-9]+)?)",
                text
            )
            if match:
                tool_name = match.group(1)
                attr = match.group(2)
                value = match.group(3)
                policy_str = f"""forbid(
    principal,
    action,
    resource
) when {{
    context.tool_name == "{tool_name}" && context.{attr} < {value}
}};"""
                explanation = f"Prevents agent from calling '{tool_name}' if the parameter '{attr}' is less than {value}."
                success = True

        # 4. Pattern: Forbid specific tool when text attribute contains substring
        # E.g., "Block execute_sql when query contains drop" or "Block query containing rm -rf"
        elif any(x in text for x in ["contain", "has", "includes", "contains"]):
            match = re.search(
                r"(?:block|forbid|stop|prevent|deny)\s+(?:the\s+tool\s+|tool\s+)?([a-zA-Z0-9_]+)\s+(?:when|if|where)\s+(?:context\.)?([a-zA-Z0-9_]+)\s+(?:contains|has|includes)\s+['\"]?([a-zA-Z0-9_\-\s\*\:\;\.\,\/]+)['\"]?",
                text
            )
            if match:
                tool_name = match.group(1)
                attr = match.group(2)
                value = match.group(3)
                policy_str = f"""forbid(
    principal,
    action,
    resource
) when {{
    context.tool_name == "{tool_name}" && "{value}" in context.{attr}
}};"""
                explanation = f"Blocks '{tool_name}' if the parameter '{attr}' contains the sensitive substring '{value}'."
                success = True

        # 5. Pattern: Global query content filter (not tied to any tool)
        # E.g., "Block queries containing rm -rf" or "Forbid input with ignore all previous instructions"
        global_match = re.search(
            r"(?:block|forbid|stop|prevent|deny)\s+(?:queries|input|inputs|commands|actions)?\s*(?:containing|with|that\s+contain)\s+['\"]?([a-zA-Z0-9_\-\s\*\:\;\.\,\/]+)['\"]?",
            text
        )
        if not success and global_match:
            value = global_match.group(1)
            policy_str = f"""forbid(
    principal,
    action,
    resource
) when {{
    "{value}" in context.query
}};"""
            explanation = f"Global safety rule blocking any agent prompt or query containing the substring '{value}'."
            success = True

        # 6. Fallback generator for generic input
        if not success:
            # Let's try to extract any tool and any condition
            # E.g. "forbid issue_refund when amount exceeds 100"
            words = text.split()
            potential_tools = [w for w in words if w not in ["block", "forbid", "prevent", "the", "tool", "when", "if", "where", "is", "a", "an", "agent", "from", "using"]]
            if potential_tools:
                tool_name = potential_tools[0]
                policy_str = f"""forbid(
    principal,
    action,
    resource
) when {{
    context.tool_name == "{tool_name}"
}};"""
                explanation = f"Generic block policy matching tool '{tool_name}' (automatically generated fallback)."
                success = True
            else:
                policy_str = ""
                explanation = "Could not parse policy intent. Please specify a rule like 'Block tool issue_refund when amount > 500'."
                success = False

        return {
            "success": success,
            "cedar_content": policy_str,
            "explanation": explanation
        }
