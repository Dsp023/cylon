#!/usr/bin/env node
/**
 * Fast visual QA preview snapshot generator.
 * Uses Playwright to load page.html and captures one high-res snapshot
 * per scene at its cue midpoint.
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

async function main() {
  const args = process.argv.slice(2);
  let dataPath = path.resolve('dist/data.js');
  let outDir = path.resolve('dist/previews');
  let templatePath = path.resolve('templates/page.html');

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--data' || args[i] === '-d') dataPath = path.resolve(args[++i]);
    if (args[i] === '--output-dir' || args[i] === '-o') outDir = path.resolve(args[++i]);
    if (args[i] === '--template' || args[i] === '-t') templatePath = path.resolve(args[++i]);
  }

  if (!fs.existsSync(dataPath)) {
    console.error(`Error: Timeline data file not found at: ${dataPath}`);
    console.error('Run "python scripts/build.py" first to generate data.js.');
    process.exit(1);
  }

  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  // Read data.js content
  const dataContent = fs.readFileSync(dataPath, 'utf8');
  let pageContent = fs.readFileSync(templatePath, 'utf8');

  // Inline data.js into page content so it loads cleanly in headless file:// URL
  pageContent = pageContent.replace('<script src="data.js"></script>', `<script>${dataContent}</script>`);

  const tempHtmlPath = path.join(outDir, 'preview_temp.html');
  fs.writeFileSync(tempHtmlPath, pageContent, 'utf8');

  console.log('=' .repeat(60));
  console.log('Generating Scene Previews (Snapshots)...');
  console.log(`Output folder: ${outDir}`);
  console.log('=' .repeat(60));

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 720, height: 1280 },
    deviceScaleFactor: 1.0,
  });
  const page = await context.newPage();

  await page.goto(`file://${path.resolve(tempHtmlPath)}`, { waitUntil: 'domcontentloaded' });

  // Read scenes from window.DATA
  const scenes = await page.evaluate(() => (typeof DATA !== 'undefined' ? DATA.scenes : []));

  if (!scenes || scenes.length === 0) {
    console.log('[!] No scenes found in data.');
    await browser.close();
    return;
  }

  for (let i = 0; i < scenes.length; i++) {
    const sc = scenes[i];
    const midTime = sc.t0 + (sc.t1 - sc.t0) * 0.5;
    await page.evaluate((t) => window.setT(t), midTime);
    // Allow small reflow
    await page.waitForTimeout(50);

    const outPath = path.join(outDir, `pv_${i}_${sc.type}.jpg`);
    await page.screenshot({ path: outPath, type: 'jpeg', quality: 90 });
    console.log(`[✓] Scene ${i + 1} (${sc.type}) @ ${midTime.toFixed(2)}s -> ${path.basename(outPath)}`);
  }

  await browser.close();

  // Clean up temp file
  try { fs.unlinkSync(tempHtmlPath); } catch (_) {}

  console.log('=' .repeat(60));
  console.log(`Done! ${scenes.length} preview snapshots generated in: ${outDir}`);
}

main().catch(err => {
  console.error('Snapshot failed:', err);
  process.exit(1);
});

