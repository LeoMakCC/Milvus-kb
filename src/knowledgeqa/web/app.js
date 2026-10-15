async function refreshStatus() {
  const health = document.getElementById("health");
  const statusLine = document.getElementById("statusLine");
  try {
    const response = await fetch("/api/v1/status");
    const data = await response.json();
    health.textContent = "已运行";
    health.className = "status ok";
    statusLine.textContent = `Milvus: ${data.milvus} | 任务: ${data.jobs_running}`;
  } catch (error) {
    health.textContent = "服务异常";
    health.className = "status bad";
    statusLine.textContent = String(error);
  }
}

refreshStatus();
setInterval(refreshStatus, 5000);
