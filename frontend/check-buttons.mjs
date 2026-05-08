import { chromium } from 'playwright';

async function check() {
  const browser = await chromium.launch({ headless: true });
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
  
  if (page.url().includes('/projects')) {
    // Click on first task
    const taskCards = await page.$$('.task-card, [class*="task"]');
    if (taskCards.length > 0) {
      await taskCards[0].click();
      await page.waitForTimeout(3000);
    }
    
    // Or try clicking on task links
    const taskLinks = await page.$$('a[href*="/review/"]');
    if (taskLinks.length > 0) {
      await taskLinks[0].click();
      await page.waitForTimeout(3000);
    }
  }
  
  console.log('Final URL:', page.url());
  
  // Take screenshot
  await page.screenshot({ path: '/tmp/final-page.png', fullPage: true });
  
  // Check all buttons with p- classes
  const buttons = await page.$$eval('button', buttons => 
    buttons.map(b => ({
      class: b.className,
      padding: window.getComputedStyle(b).padding,
      computedPad: b.className.match(/p-\d+\.?\d*/)?.[0] || 'no-p-class'
    }))
  );
  
  console.log('\n=== Buttons with padding classes and rounded-lg ===');
  buttons.forEach((b, i) => {
    if (b.class.includes('rounded-lg')) {
      console.log(`Button ${i}:`);
      console.log(`  Class in HTML: "${b.computedPad}"`);
      console.log(`  Actual computed padding: "${b.padding}"`);
      console.log(`  Full class: "${b.class.slice(0, 100)}..."`);
    }
  });
  
  await browser.close();
}

check().catch(console.error);
