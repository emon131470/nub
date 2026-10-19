import "dotenv/config";
import express from "express";
import rateLimit from "express-rate-limit";
import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import Database from "better-sqlite3";
import { InferenceClient } from "@huggingface/inference";
import path from "node:path";
import { fileURLToPath } from "node:url";

const { HF_TOKEN, JWT_SECRET, ADMIN_KEY, DB_PATH = "./data.db", FREE_CREDITS = "10" } = process.env;
if (!HF_TOKEN || !JWT_SECRET) { console.error("Set HF_TOKEN and JWT_SECRET in .env"); process.exit(1); }

const MODELS = {
  Image: process.env.MODEL_IMAGE || "black-forest-labs/FLUX.1-schnell",
  Chat: process.env.MODEL_CHAT || "Qwen/Qwen2.5-72B-Instruct",
  Voice: process.env.MODEL_VOICE || "hexgrad/Kokoro-82M",
  Video: process.env.MODEL_VIDEO || "Wan-AI/Wan2.2-TI2V-5B",
};
const COST = { Image: 1, "Ad creator": 1, Voice: 2, Video: 5 };

const db = new Database(DB_PATH);
db.exec(`CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL,
  hash TEXT NOT NULL, credits INTEGER NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP)`);

const hf = new InferenceClient(HF_TOKEN);
const app = express();
app.set("trust proxy", 1);
app.use(express.json({ limit: "20kb" }));
app.use(express.static(path.join(path.dirname(fileURLToPath(import.meta.url)), "public")));

const sign = u => jwt.sign({ id: u.id }, JWT_SECRET, { expiresIn: "30d" });
const pub = u => ({ email: u.email, credits: u.credits });

function auth(req, res, next) {
  const t = (req.headers.authorization || "").replace("Bearer ", "");
  try {
    const { id } = jwt.verify(t, JWT_SECRET);
    const u = db.prepare("SELECT * FROM users WHERE id=?").get(id);
    if (!u) throw new Error();
    req.user = u; next();
  } catch { res.status(401).json({ error: "Log in to continue." }); }
}

const authLimit = rateLimit({ windowMs: 15 * 60 * 1000, max: 30 });
const genLimit = rateLimit({ windowMs: 60 * 1000, max: 15, keyGenerator: r => String(r.user?.id || r.ip) });

app.post("/api/register", authLimit, (req, res) => {
  const email = String(req.body.email || "").trim().toLowerCase();
  const password = String(req.body.password || "");
  if (!/^\S+@\S+\.\S+$/.test(email)) return res.status(400).json({ error: "Enter a valid email." });
  if (password.length < 8) return res.status(400).json({ error: "Use a password with at least 8 characters." });
  if (db.prepare("SELECT 1 FROM users WHERE email=?").get(email)) return res.status(409).json({ error: "That email already has an account. Log in instead." });
  const info = db.prepare("INSERT INTO users(email,hash,credits) VALUES(?,?,?)").run(email, bcrypt.hashSync(password, 10), Number(FREE_CREDITS));
  const u = db.prepare("SELECT * FROM users WHERE id=?").get(info.lastInsertRowid);
  res.json({ token: sign(u), user: pub(u) });
});

app.post("/api/login", authLimit, (req, res) => {
  const email = String(req.body.email || "").trim().toLowerCase();
  const u = db.prepare("SELECT * FROM users WHERE email=?").get(email);
  if (!u || !bcrypt.compareSync(String(req.body.password || ""), u.hash)) return res.status(401).json({ error: "Email or password is wrong." });
  res.json({ token: sign(u), user: pub(u) });
});

app.get("/api/me", auth, (req, res) => res.json({ user: pub(req.user) }));

app.post("/api/generate", auth, genLimit, async (req, res) => {
  const tool = String(req.body.tool || "");
  const prompt = String(req.body.prompt || "").trim();
  const cost = COST[tool];
  if (!cost) return res.status(400).json({ error: "Unknown tool." });
  if (!prompt) return res.status(400).json({ error: "Enter a prompt first." });
  if (prompt.length > 600) return res.status(400).json({ error: "Keep your prompt under 600 characters." });

  const take = db.prepare("UPDATE users SET credits=credits-? WHERE id=? AND credits>=?").run(cost, req.user.id, cost);
  if (!take.changes) return res.status(402).json({ error: "You're out of credits. Choose a plan to continue." });

  try {
    let out;
    if (tool === "Ad creator") {
      const r = await hf.chatCompletion({
        model: MODELS.Chat, max_tokens: 500,
        messages: [
          { role: "system", content: "You write short social media ads. Reply with: Headline, Caption (2 sentences), 5 hashtags, and a Call to action. Plain text only." },
          { role: "user", content: prompt }]
      });
      out = { type: "text", text: r.choices[0].message.content };
    } else {
      const blob = tool === "Image" ? await hf.textToImage({ model: MODELS.Image, inputs: prompt })
        : tool === "Voice" ? await hf.textToSpeech({ model: MODELS.Voice, inputs: prompt })
        : await hf.textToVideo({ model: MODELS.Video, inputs: prompt });
      const mime = blob.type || (tool === "Image" ? "image/png" : tool === "Voice" ? "audio/wav" : "video/mp4");
      out = { type: tool.toLowerCase(), url: `data:${mime};base64,${Buffer.from(await blob.arrayBuffer()).toString("base64")}` };
    }
    const u = db.prepare("SELECT credits FROM users WHERE id=?").get(req.user.id);
    res.json({ ...out, credits: u.credits });
  } catch (e) {
    db.prepare("UPDATE users SET credits=credits+? WHERE id=?").run(cost, req.user.id);
    console.error(tool, e?.message || e);
    res.status(502).json({ error: "Couldn't generate that. Your credits were returned. Try again in a moment." });
  }
});

app.post("/api/admin/credits", (req, res) => {
  if (!ADMIN_KEY || req.headers["x-admin-key"] !== ADMIN_KEY) return res.status(403).json({ error: "Not allowed." });
  const r = db.prepare("UPDATE users SET credits=credits+? WHERE email=?").run(Number(req.body.amount) || 0, String(req.body.email || "").toLowerCase());
  res.json({ updated: r.changes });
});

const port = process.env.PORT || 3000;
app.listen(port, () => console.log("Lumora running on port " + port));
