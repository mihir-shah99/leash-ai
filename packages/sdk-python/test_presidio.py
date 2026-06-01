from agentshield.pii import PIIRedactor

payload = {
    "query": "Can you check the balance for Alice Smith? Her SSN is 123-45-6789 and email is alice.smith@example.com",
    "metadata": {
        "user_phone": "Call me at 555-123-4567 to confirm."
    }
}

print("Original Payload:")
print(payload)

redacted = PIIRedactor.redact_payload(payload)

print("\nRedacted Payload:")
print(redacted)
