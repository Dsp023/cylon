
#!/usr/bin/env node
/**
 * Playwright frame-by-frame renderer piped directly into ffmpeg.
 * Zero dropped frames, deterministic timing.
 */

const { chromium } = require('playwright');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

function findFFmpeg() {
  const localAppData = process.env.LOCALAPPDATA || '';
  const candidates = [
    'ffmpeg',
    path.join(localAppData, 'Microsoft', 'WinGet', 'Packages', 'Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe', 'ffmpeg-8.0.1-full_build', 'bin', 'ffmpeg.exe'),
  ];
  for (const c of candidates) {
    if (c === 'ffmpeg') continue;
    if (fs.existsSync(c)) return c;
  }
  return 'ffmpeg';
}

async function main() {
  const args = process.argv.slice(2);
  let dataPath = path.resolve('dist/data.js');
  let metaPath = path.resolve('dist/meta.json');
  let outVideo = path.resolve('dist/tmp_short.mp4');
  let templatePath = path.resolve('templates/page.html');
  let fps = 30;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--data' || args[i] === '-d') dataPath = path.resolve(args[++i]);
    if (args[i] === '--meta' || args[i] === '-m') metaPath = path.resolve(args[++i]);
    if (args[i] === '--output' || args[i] === '-o') outVideo = path.resolve(args[++i]);
    if (args[i] === '--template' || args[i] === '-t') templatePath = path.resolve(args[++i]);
    if (args[i] === '--fps') fps = parseInt(args[++i], 10) || 30;
  }

  if (!fs.existsSync(dataPath)) {
    console.error(`Error: Data file not found: ${dataPath}`);
    console.error('Run "python scripts/build.py" first.');
    process.exit(1);
  }

  const outDir = path.dirname(outVideo);
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

  // Read data and metadata
  const dataContent = fs.readFileSync(dataPath, 'utf8');
  let totalSeconds = 30.0;

  if (fs.existsSync(metaPath)) {
    const meta = JSON.parse(fs.readFileSync(metaPath, 'utf8'));
    totalSeconds = meta.total || totalSeconds;
    fps = meta.fps || fps;
  }

  const totalFrames = Math.ceil(totalSeconds * fps);

  console.log('=' .repeat(60));
  console.log('Rendering Video Frames with Playwright -> ffmpeg');
  console.log(`Duration: ${totalSeconds}s | FPS: ${fps} | Total Frames: ${totalFrames}`);
  console.log(`Output: ${outVideo}`);
  console.log('=' .repeat(60));

  // Prepare HTML with inlined data
  let pageContent = fs.readFileSync(templatePath, 'utf8');
  pageContent = pageContent.replace('<script src="data.js"></script>', `<script>${dataContent}</script>`);
  const tempHtmlPath = path.join(outDir, 'render_temp.html');
  fs.writeFileSync(tempHtmlPath, pageContent, 'utf8');

  // Spawn ffmpeg receiving JPEG image stream over stdin
  const ffmpegArgs = [
    '-y',
    '-f', 'image2pipe',
    '-vcodec', 'mjpeg',
    '-r', String(fps),
    '-i', '-',
    '-c:v', 'libx264',
    '-pix_fmt', 'yuv420p',
    '-preset', 'veryfast',
    '-crf', '19',
    outVideo
  ];

  const ffmpeg = spawn(findFFmpeg(), ffmpegArgs, { stdio: ['pipe', 'inherit', 'inherit'] });

  ffmpeg.on('error', (err) => {
    console.error('[!] Failed to spawn ffmpeg:', err.message);
    console.error('Please ensure ffmpeg is installed and available in your PATH.');
    process.exit(1);
  });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 720, height: 1280 },
    deviceScaleFactor: 1.0,
  });
  const page = await context.newPage();

  await page.goto(`file://${path.resolve(tempHtmlPath)}`, { waitUntil: 'domcontentloaded' });

  const dt = 1.0 / fps;
  const startTime = Date.now();

  for (let frame = 0; frame < totalFrames; frame++) {
    const t = frame * dt;
    await page.evaluate((currentTime) => window.setT(currentTime), t);

    const buffer = await page.screenshot({ type: 'jpeg', quality: 95 });

    // Stream buffer into ffmpeg pipe
    const canWrite = ffmpeg.stdin.write(buffer);
    if (!canWrite) {
      await new Promise(resolve => ffmpeg.stdin.once('drain', resolve));
    }

    if (frame % 30 === 0 || frame === totalFrames - 1) {
      const pct = Math.round((frame / totalFrames) * 100);
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      const fpsRendered = (frame / ((Date.now() - startTime) / 1000 || 1)).toFixed(1);
      process.stdout.write(`\r[${pct}%] Frame ${frame}/${totalFrames} (${t.toFixed(1)}s) - ${fpsRendered} fps (${elapsed}s elapsed)`);
    }
  }

  process.stdout.write('\nFinishing video encoding in ffmpeg...\n');
  ffmpeg.stdin.end();

  await new Promise((resolve) => ffmpeg.on('close', resolve));
  await browser.close();

  try { fs.unlinkSync(tempHtmlPath); } catch (_) {}

  const totalTime = ((Date.now() - startTime) / 1000).toFixed(1);
  console.log('=' .repeat(60));
  console.log(`[✓] Visual render complete in ${totalTime}s! File: ${outVideo}`);
  console.log('=' .repeat(60));
}

main().catch(err => {
  console.error('Render error:', err);
  process.exit(1);
});

