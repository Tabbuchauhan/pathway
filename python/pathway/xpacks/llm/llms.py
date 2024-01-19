# Copyright © 2024 Pathway
"""
UDF for calling LLMs:
1. wrappers over LLM APIs
2. prompt building tools
"""

import openai as openai_mod

import pathway as pw
from pathway.internals import asynchronous


class OpenAIChat(pw.UDFAsync):
    """Pathway wrapper for OpenAI Chat services.

    The capacity, retry_strategy and cache_strategy need to be specified during object
    construction. All other arguments can be overridden during application.

    Parameters:
    - capacity: Maximum number of concurrent operations allowed.
        Defaults to None, indicating no specific limit.
    - retry_strategy: Strategy for handling retries in case of failures.
        Defaults to None.
    - cache_strategy: Defines the caching mechanism. If set to None and a persistency
        is enabled, operations will be cached using the persistence layer.
        Defaults to None.
    - model: ID of the model to use. See the
      [model endpoint compatibility](https://platform.openai.com/docs/models/model-endpoint-compatibility)
      table for details on which models work with the Chat API.
    - frequency_penalty: Number between -2.0 and 2.0. Positive values penalize new tokens based on their
        existing frequency in the text so far, decreasing the model's likelihood to
        repeat the same line verbatim.

        [See more information about frequency and presence penalties.](
            https://platform.openai.com/docs/guides/text-generation/parameter-details)
    - function_call: Deprecated in favor of `tool_choice`.

        Controls which (if any) function is called by the model. `none` means the model
        will not call a function and instead generates a message. `auto` means the model
        can pick between generating a message or calling a function. Specifying a
        particular function via `{"name": "my_function"}` forces the model to call that
        function.

        `none` is the default when no functions are present. `auto` is the default if
        functions are present.
    - functions: Deprecated in favor of `tools`.

        A list of functions the model may generate JSON inputs for.
    - logit_bias: Modify the likelihood of specified tokens appearing in the completion.

        Accepts a JSON object that maps tokens (specified by their token ID in the
        tokenizer) to an associated bias value from -100 to 100. Mathematically, the
        bias is added to the logits generated by the model prior to sampling. The exact
        effect will vary per model, but values between -1 and 1 should decrease or
        increase likelihood of selection; values like -100 or 100 should result in a ban
        or exclusive selection of the relevant token.
    - logprobs: Whether to return log probabilities of the output tokens or not. If true,
        returns the log probabilities of each output token returned in the `content` of
        `message`. This option is currently not available on the `gpt-4-vision-preview`
        model.
    - max_tokens: The maximum number of [tokens](/tokenizer) that can be generated in the chat
        completion.

        The total length of input tokens and generated tokens is limited by the model's
        context length.
        [Example Python code](https://cookbook.openai.com/examples/how_to_count_tokens_with_tiktoken)
        for counting tokens.
    - n: How many chat completion choices to generate for each input message. Note that
        you will be charged based on the number of generated tokens across all of the
        choices. Keep `n` as `1` to minimize costs.
    - presence_penalty: Number between -2.0 and 2.0. Positive values penalize new tokens based on
        whether they appear in the text so far, increasing the model's likelihood to
        talk about new topics.

        [See more information about frequency and presence penalties.](
            https://platform.openai.com/docs/guides/text-generation/parameter-details)
    - response_format: An object specifying the format that the model must output. Compatible with
        `gpt-4-1106-preview` and `gpt-3.5-turbo-1106`.

        Setting to `{ "type": "json_object" }` enables JSON mode, which guarantees the
        message the model generates is valid JSON.

        **Important:** when using JSON mode, you **must** also instruct the model to
        produce JSON yourself via a system or user message. Without this, the model may
        generate an unending stream of whitespace until the generation reaches the token
        limit, resulting in a long-running and seemingly "stuck" request. Also note that
        the message content may be partially cut off if `finish_reason="length"`, which
        indicates the generation exceeded `max_tokens` or the conversation exceeded the
        max context length.
    - seed: This feature is in Beta. If specified, our system will make a best effort to
        sample deterministically, such that repeated requests with the same `seed` and
        parameters should return the same result. Determinism is not guaranteed, and you
        should refer to the `system_fingerprint` response parameter to monitor changes
        in the backend.
    - stop: Up to 4 sequences where the API will stop generating further tokens.
    - stream: If set, partial message deltas will be sent, like in ChatGPT. Tokens will be
        sent as data-only
        [server-sent events](
            https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events#Event_stream_format)
        as they become available, with the stream terminated by a `data: [DONE]`
        message.
        [Example Python code](https://cookbook.openai.com/examples/how_to_stream_completions).
    - temperature: What sampling temperature to use, between 0 and 2. Higher values like 0.8 will
        make the output more random, while lower values like 0.2 will make it more
        focused and deterministic.

        We generally recommend altering this or `top_p` but not both.
    - tool_choice: Controls which (if any) function is called by the model. `none` means the model
        will not call a function and instead generates a message. `auto` means the model
        can pick between generating a message or calling a function. Specifying a
        particular function via
        `{"type: "function", "function": {"name": "my_function"}}` forces the model to
        call that function.

        `none` is the default when no functions are present. `auto` is the default if
        functions are present.
    - tools: A list of tools the model may call. Currently, only functions are supported as a
        tool. Use this to provide a list of functions the model may generate JSON inputs
        for.
    - top_logprobs: An integer between 0 and 5 specifying the number of most likely tokens to return
        at each token position, each with an associated log probability. `logprobs` must
        be set to `true` if this parameter is used.
    - top_p: An alternative to sampling with temperature, called nucleus sampling, where the
        model considers the results of the tokens with top_p probability mass. So 0.1
        means only the tokens comprising the top 10% probability mass are considered.

        We generally recommend altering this or `temperature` but not both.
    - user: A unique identifier representing your end-user, which can help OpenAI to monitor
        and detect abuse.
        [Learn more](https://platform.openai.com/docs/guides/safety-best-practices/end-user-ids).
    - extra_headers: Send extra headers
    - extra_query: Add additional query parameters to the request
    - extra_body: Add additional JSON properties to the request
    - timeout: Override the client-level default timeout for this request, in seconds


    Any arguments can be provided either to the constructor or in the UDF call.
    To specify the `model` in the UDF call, set it to None.

    Examples:
    >>> import pathway as pw
    >>> from pathway.xpacks.llm import llms
    >>> from pathway.internals.asynchronous import ExponentialBackoffRetryStrategy
    >>> chat = llms.OpenAIChat(model=None, retry_strategy=ExponentialBackoffRetryStrategy(max_retries=6))
    >>> t = pw.debug.table_from_markdown('''
    ... txt     | model
    ... Wazzup? | gpt-3.5-turbo
    ... ''')
    >>> r = t.select(ret=chat(llms.prompt_chat_single_qa(t.txt), model=t.model))
    >>> r
    <pathway.Table schema={'ret': str | None}>
    """

    def __init__(
        self,
        capacity: int | None = None,
        retry_strategy: asynchronous.AsyncRetryStrategy | None = None,
        cache_strategy: asynchronous.CacheStrategy | None = None,
        model: str | None = "gpt-3.5-turbo",
        **openai_kwargs,
    ):
        super().__init__(
            capacity=capacity,
            retry_strategy=retry_strategy,
            cache_strategy=cache_strategy,
        )
        self.kwargs = dict(openai_kwargs)
        if model is not None:
            self.kwargs["model"] = model

    async def __wrapped__(self, messages: list[dict] | pw.Json, **kwargs) -> str | None:
        if isinstance(messages, pw.Json):
            messages_decoded: list[openai_mod.ChatCompletionMessageParam] = messages.value  # type: ignore
        else:
            messages_decoded = messages

        kwargs = {**self.kwargs, **kwargs}
        api_key = kwargs.pop("api_key", None)
        client = openai_mod.AsyncOpenAI(api_key=api_key)
        ret = await client.chat.completions.create(messages=messages_decoded, **kwargs)
        return ret.choices[0].message.content


@pw.udf
def prompt_chat_single_qa(question: str) -> pw.Json:
    """Create chat prompt messages for single question answering."""
    return pw.Json([dict(role="system", content=question)])
