forbid(
    principal,
    action,
    resource
) when {
    "rm -rf" in context.query
};

forbid(
    principal,
    action,
    resource
) when {
    "drop table" in context.query
};

forbid(
    principal,
    action,
    resource
) when {
    "ignore all previous instructions" in context.query
};
