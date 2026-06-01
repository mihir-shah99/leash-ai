forbid(
    principal,
    action,
    resource
) when {
    context.tool_name == "issue_refund" && context.amount > "500"
};
