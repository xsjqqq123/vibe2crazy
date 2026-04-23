module.exports = {
  testDir: './',
  testMatch: '**/test-refresh.spec.ts',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:5173',
    headless: true,
    channel: 'chrome',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        channel: 'chrome',
        launchOptions: {
          executablePath: '/usr/bin/google-chrome',
        },
      },
    },
  ],
};
