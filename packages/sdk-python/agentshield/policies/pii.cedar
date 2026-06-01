forbid(
    principal,
    action,
    resource
) when {
    context.tool_name == "extract_pii" 
};
