const fs = require("fs/promises");
const path = require("path");

const AUDIO_EXTS = new Set([".mp3", ".m4a", ".wav", ".flac", ".aac", ".ogg"]);
const IMAGE_EXTS = new Set([".jpg", ".jpeg", ".png", ".webp", ".avif"]);
const DARK_PALETTE = [
  "#2a2f3a",
  "#2f2a3a",
  "#2a3a35",
  "#3a2f2a",
  "#2a333a",
  "#3a2a33",
  "#33362a",
  "#2a2a2f"
];

function pickColor(seed) {
  let h = 0;
  for (let i = 0; i < seed.length; i += 1) h = (h * 31 + seed.charCodeAt(i)) | 0;
  const idx = Math.abs(h) % DARK_PALETTE.length;
  return DARK_PALETTE[idx];
}

function normalizeAlbumName(raw) {
  return String(raw || "")
    .replace(/\[[^\]]*]/g, " ")
    .replace(/\([^)]*\)/g, " ")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function splitArtistAlbum(folderName) {
  const clean = normalizeAlbumName(folderName);
  const parts = clean.split(" - ");
  if (parts.length >= 2) {
    return {
      author: parts[0].trim().toUpperCase(),
      name: parts.slice(1).join(" - ").trim().toUpperCase()
    };
  }
  return { author: "UNKNOWN ARTIST", name: clean.toUpperCase() || "UNKNOWN ALBUM" };
}

async function scanAlbum(folderPath, folderName) {
  let entries = [];
  try {
    entries = await fs.readdir(folderPath, { withFileTypes: true });
  } catch (_) {
    return null;
  }

  const files = entries.filter((e) => e.isFile()).map((e) => e.name);
  const tracks = files
    .filter((f) => AUDIO_EXTS.has(path.extname(f).toLowerCase()))
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" }));
  if (!tracks.length) return null;

  const cover = files
    .filter((f) => IMAGE_EXTS.has(path.extname(f).toLowerCase()))
    .sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }))[0];

  const parsed = splitArtistAlbum(folderName);
  const relFolder = `Vinyl Collection/${folderName}`;
  return {
    name: parsed.name,
    author: parsed.author,
    color: pickColor(`${parsed.author}-${parsed.name}`),
    duration: "",
    folder: relFolder,
    cover: cover ? `${relFolder}/${cover}` : "",
    tracks
  };
}

module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store, max-age=0, must-revalidate");
  res.setHeader("Pragma", "no-cache");
  res.setHeader("Expires", "0");

  const root = process.cwd();
  const collectionRoot = path.join(root, "Vinyl Collection");

  try {
    const dirs = await fs.readdir(collectionRoot, { withFileTypes: true });
    const albums = [];
    for (const dir of dirs) {
      if (!dir.isDirectory()) continue;
      const album = await scanAlbum(path.join(collectionRoot, dir.name), dir.name);
      if (album) albums.push(album);
    }
    albums.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }));
    res.status(200).json(albums);
    return;
  } catch (err) {
    res.status(500).json({ error: "Failed to scan collection", details: String(err?.message || err) });
  }
};

