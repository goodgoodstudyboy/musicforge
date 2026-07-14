function continuityReceiverBase() {
  const programId = $("continuity-receiver-program-id").value.trim();
  if (!programId) throw new Error("Program ID is required.");
  return `/api/unified-release-programs/${encodeURIComponent(programId)}/continuity-command-center-acceptance`;
}

async function showContinuityReceiver(path, options = {}) {
  const data = await api(path, options);
  $("continuity-receiver-status").textContent = data.status || (data.report || {}).status || (data.verification || {}).status || "updated";
  $("continuity-receiver-result").textContent = JSON.stringify(data, null, 2);
  return data;
}

function continuityReceiverChangeBase() {
  return `${continuityReceiverBase()}/change-control`;
}

Object.assign(globalThis, { continuityReceiverBase, showContinuityReceiver, continuityReceiverChangeBase });

export { continuityReceiverBase, showContinuityReceiver, continuityReceiverChangeBase };
