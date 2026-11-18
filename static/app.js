let data = { conversations: [], messages: [], alerts: [] };
let selected = null;
let filter = "open";

const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
}[char]));

function toast(message) {
  const node = $("#toast");
  node.textContent = message;
  node.classList.add("visible");
  setTimeout(() => node.classList.remove("visible"), 3200);
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" }, ...options
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Ошибка запроса");
  return result;
}

function render() {
  const open = data.alerts.filter((item) => item.status === "open");
  $("#question-count").textContent = open.filter((item) => item.kind === "question").length;
  $("#commitment-count").textContent = open.filter((item) => item.kind === "commitment").length;
  $("#done-count").textContent = data.alerts.filter((item) => item.status === "done").length;
  $("#chat-count").textContent = data.conversations.length;

  $("#chat-list").innerHTML = data.conversations.map((chat) => {
    const count = open.filter((item) => item.conversation_id === chat.id).length;
    const latest = data.messages.filter((item) => item.conversation_id === chat.id).at(-1);
    return `<button class="chat ${selected === chat.id ? "selected" : ""}" data-chat="${chat.id}">
      <span class="avatar">${escapeHtml(chat.title.slice(0, 1))}</span><span class="chat-copy"><b>${escapeHtml(chat.title)}</b><small>${escapeHtml(latest?.text || chat.context)}</small></span>${count ? `<em>${count}</em>` : ""}</button>`;
  }).join("");

  const chat = data.conversations.find((item) => item.id === selected);
  $("#thread-title").textContent = chat?.title || "Выберите диалог";
  $("#thread-context").textContent = chat?.context || "";
  $("#messages").innerHTML = data.messages.filter((item) => item.conversation_id === selected).map((item) =>
    `<div class="message ${item.author}"><span>${item.author === "team" ? "Команда" : "Клиент"}</span><p>${escapeHtml(item.text)}</p><small>${new Date(item.created_at).toLocaleString("ru-RU")}</small></div>`
  ).join("");
  $("#messages").scrollTop = $("#messages").scrollHeight;

  const visible = data.alerts.filter((item) => item.conversation_id === selected && (filter === "all" || item.status === "open"));
  $("#alert-list").innerHTML = visible.length ? visible.map((item) => {
    const message = data.messages.find((entry) => entry.id === item.message_id);
    const isQuestion = item.kind === "question";
    const title = isQuestion ? "Вопрос без ответа" : "Обещание команды";
    const due = item.due_date ? `<span class="due">Срок ${escapeHtml(item.due_date)}</span>` : "";
    return `<article class="alert ${item.status}"><div class="alert-top"><span class="kind ${item.kind}">${isQuestion ? "?" : "✓"}</span><div><b>${title}</b><small>${item.status === "done" ? "Закрыто" : "Открыто"}</small></div></div><p>${escapeHtml(message?.text || "")}</p>${due}<button data-alert="${item.id}" data-status="${item.status === "open" ? "done" : "open"}">${item.status === "open" ? "Отметить выполненным" : "Вернуть в работу"}</button></article>`;
  }).join("") : `<div class="empty"><span>◎</span><b>Сигналов нет</b><p>Добавьте сообщение с вопросом или обещанием, чтобы проверить работу сервиса.</p></div>`;
}

async function refresh() {
  data = await request("/api/state");
  if (!selected) selected = data.conversations[0]?.id;
  render();
}

$("#chat-list").addEventListener("click", (event) => {
  const button = event.target.closest("[data-chat]");
  if (!button) return;
  selected = Number(button.dataset.chat);
  render();
});

$("#alert-list").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-alert]");
  if (!button) return;
  try {
    await request(`/api/alerts/${button.dataset.alert}`, {
      method: "PATCH", body: JSON.stringify({ status: button.dataset.status })
    });
    await refresh();
    toast("Статус сигнала обновлён");
  } catch (error) { toast(error.message); }
});

document.querySelectorAll("[data-filter]").forEach((button) => button.addEventListener("click", () => {
  filter = button.dataset.filter;
  document.querySelectorAll("[data-filter]").forEach((item) => item.classList.toggle("selected", item === button));
  render();
}));

$("#message-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = $("#message").value.trim();
  if (!text || !selected) return;
  const button = $("#message-form button[type=submit]");
  button.disabled = true;
  try {
    await request("/api/messages", {
      method: "POST", body: JSON.stringify({ conversation_id: selected, author: $("#author").value, text })
    });
    $("#message").value = "";
    await refresh();
    toast("Сообщение добавлено");
  } catch (error) { toast(error.message); }
  finally { button.disabled = false; }
});

refresh().catch((error) => toast(error.message));
