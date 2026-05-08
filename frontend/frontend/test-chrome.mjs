import { chromium } from 'playwright';

async function check() {
  // 使用 Chrome channel 者使用 chromium
  const browser = await chromium.launch({ 
    channel: 'chrome',  // 使用系统安装的 Chrome
    headless: false     // 非无头模式，可以看到浏览器
  });
  
  const page = await browser.newPage();
  
  // Go to login page
  await page.goto('http://localhost:5173/login', { waitUntil: 'networkidle' });
  console.log('Login page URL:', page.url());
  
  // Login with correct password
  const passwordInput = await page.$('input[type="password"]');
  if (passwordInput) {
    await passwordInput.fill('13559969');
    await page.click('button.btn-primary');
    await page.waitForTimeout(2000);
    console.log('After login URL:', page.url());
  }
  
  // Navigate to a task if on projects page
  await page.waitForTimeout(1000);
  
  // Take screenshot of projects page header buttons
  await page.screenshot({ path: '/tmp/projects-header.png', clip: { x: 0, y: 0, width: 1280, height: 100 } });
  console.log('Screenshot saved: /tmp/projects-header.png');
  
  // Check buttons with rounded-lg class
  const buttons = await page.$$eval('button.rounded-lg, button[class*="rounded-lg"]', buttons => 
    buttons.map(b => ({
      class: b.className,
      padding: window.getComputedStyle(b).padding,
      width: b.offsetWidth,
      height: b.offsetHeight
    }))
  );
  
  console.log('\n=== Buttons with rounded-lg class ===');
  buttons.slice(0, 10).forEach((b, i) => {
    console.log(`Button ${i}:`);
    console.log(`  padding: "${b.padding}"`);
    console.log(`  size: ${b.width}x${b.height}px`);
    console.log(`  class: "${b.class.slice(0, 60)}..."`);
  });
  
  // Try to navigate to CodeReviewView by clicking on a task
  const taskCards = await page.$$('.task-card, [class*="cursor-pointer"][class*="hover"]');
  if (taskCards.length > 0) {
    console.log('\nClicking on first task...');
    await taskCards[0].click();
    await page.waitForTimeout(3000);
    console.log('After task click URL:', page.url());
    
    // Screenshot of CodeReviewView header
    await page.screenshot({ path: '/tmp/codereview-header.png', clip: { x: 0, y: 0, width: 1280, height: 100 } });
    console.log('Screenshot saved: /tmp/codereview-header.png');
    
    // Check buttons again
    const reviewButtons = await page.$$eval('button.rounded-lg, button[class*="rounded-lg"]', buttons => 
      buttons.map(b => ({
        class: b.className,
        padding: window.getComputedStyle(b).padding,
        width: b.offsetWidth,
        height: b.offsetHeight
      }))
    );
    
    console.log('\n=== CodeReviewView Buttons ===');
    reviewButtons.slice(0, 15).forEach((b, i) => {
      console.log(`Button ${i}:`);
      console.log(`  padding: "${b.padding}"`);
      console.log(`  size: ${b.width}x${b.height}px`);
    });
  }
  
  // Keep browser open for 10 seconds so user can see
  console.log('\nBrowser will close in 10 seconds...');
  await page.waitForTimeout(10000);
  
  await browser.close();
}

check().catch(console.error);
