import OpenAI from "openai";

const [serverUrl, traceId, apiKey = "compatflow", sdkVersion = "unknown"] = process.argv.slice(2);
if (!serverUrl || !traceId) {
  process.stderr.write("usage: node observe.mjs <server-url> <trace-id> [api-key]\n");
  process.exit(2);
}

function mergeName(current, incoming) {
  if (!incoming || incoming === current) return current;
  if (incoming.startsWith(current)) return incoming;
  return current + incoming;
}

const partialCalls = new Map();
let chunksSeen = 0;
let finishReason = null;
let failure = null;

try {
  const client = new OpenAI({
    apiKey,
    baseURL: `${serverUrl.replace(/\/$/, "")}/v1`,
    maxRetries: 0,
    timeout: 10_000,
  });
  const stream = await client.chat.completions.create({
    model: `compatflow/${traceId}`,
    messages: [{ role: "user", content: `Replay trace ${traceId}` }],
    stream: true,
  });
  for await (const chunk of stream) {
    chunksSeen += 1;
    for (const choice of chunk.choices ?? []) {
      if (choice.index !== 0) continue;
      if (choice.finish_reason != null) finishReason = choice.finish_reason;
      for (const delta of choice.delta?.tool_calls ?? []) {
        const current = partialCalls.get(delta.index) ?? {
          index: delta.index,
          call_id: null,
          name: "",
          argument_parts: [],
        };
        if (delta.id) current.call_id = delta.id;
        current.name = mergeName(current.name, delta.function?.name);
        if (delta.function?.arguments != null) {
          current.argument_parts.push(delta.function.arguments);
        }
        partialCalls.set(delta.index, current);
      }
    }
  }
} catch (error) {
  failure = {
    kind: "sdk_error",
    exception_type: error?.constructor?.name ?? "Error",
    message: String(error?.message ?? error),
  };
}

const toolCalls = [...partialCalls.values()]
  .sort((left, right) => left.index - right.index)
  .map((call) => {
    const rawArguments = call.argument_parts.join("");
    let argumentsValue = null;
    let parseError = null;
    try {
      argumentsValue = JSON.parse(rawArguments);
    } catch (error) {
      parseError = String(error?.message ?? error);
    }
    return {
      index: call.index,
      call_id: call.call_id,
      name: call.name || null,
      arguments: argumentsValue,
      raw_arguments: rawArguments,
      parse_error: parseError,
    };
  });

process.stdout.write(
  `${JSON.stringify({
    trace_id: traceId,
    adapter: "openai-node",
    adapter_version: sdkVersion,
    chunks_seen: chunksSeen,
    finish_reason: finishReason,
    tool_calls: toolCalls,
    failure,
  })}\n`,
);
