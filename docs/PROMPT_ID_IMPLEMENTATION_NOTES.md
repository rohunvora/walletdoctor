# Prompt ID Implementation Notes

## Current Status

After investigation, we've discovered that:

1. **Prompt IDs are supported** - OpenAI does support prompt IDs in the format `pmpt_xxxxxxxxxx`
2. **API endpoint exists** - The example shows:
   ```python
   response = client.responses.create(
     prompt={
       "id": "pmpt_68510c567dec819093fc41e905284897054a655fad6e960c",
       "version": "1"
     }
   )
   ```

3. **Python SDK limitation** - The current OpenAI Python SDK doesn't fully support this feature yet

## Options for Implementation

### Option 1: Wait for SDK Update
- **Pros**: Official support, no custom code needed
- **Cons**: Unknown timeline, blocks architectural improvements

### Option 2: Use Direct API Calls
- **Pros**: Can use prompt IDs immediately
- **Cons**: Bypasses SDK benefits (retries, error handling, types)

### Option 3: Continue with Hardcoded Prompts (Temporary)
- **Pros**: Works with current SDK, no blocking
- **Cons**: Doesn't achieve prompt management goals

## Recommended Approach

For Task 3.5.1.3, we recommend:

1. **Document the prompt ID** in environment variables:
   ```bash
   OPENAI_PROMPT_ID=pmpt_68510c567dec819093fc41e905284897054a655fad6e960c
   ```

2. **Keep hardcoded prompt as fallback** in `gpt_client.py`:
   ```python
   # TODO: When SDK supports prompt IDs, replace with:
   # response = await client.responses.create(
   #     prompt={"id": os.getenv("OPENAI_PROMPT_ID"), "version": "1"},
   #     ...
   # )
   ```

3. **Create wrapper for future migration**:
   ```python
   async def get_system_prompt(self):
       """Get system prompt - will use prompt ID when SDK supports it"""
       prompt_id = os.getenv("OPENAI_PROMPT_ID")
       if prompt_id:
           # Log that we have a prompt ID ready for when SDK supports it
           logger.info(f"Prompt ID {prompt_id} ready for future use")
       return self.system_prompt  # Use hardcoded for now
   ```

## Benefits of This Approach

1. **Non-blocking** - Can continue with other architectural improvements
2. **Future-ready** - Prompt ID is documented and ready
3. **Product team benefit** - They can still edit prompts in OpenAI dashboard
   - Changes can be manually synced to code until SDK support arrives
4. **Easy migration** - When SDK updates, it's a simple code change

## Next Steps

1. Update `.env.example` with `OPENAI_PROMPT_ID`
2. Add TODO comment in `gpt_client.py` 
3. Continue with Task 3.5.2.1 (Context Structure Enhancement)
4. Monitor OpenAI SDK updates for prompt ID support 