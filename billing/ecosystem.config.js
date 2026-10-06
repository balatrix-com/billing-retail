module.exports = {
  apps: [
    {
      name: "billing-processor",
      script: "src/main.py",
      interpreter: "venwin/Scripts/python.exe", // Using the virtual environment's python
      cwd: "c:/billing",
      watch: false,
      autorestart: true,
      max_memory_restart: "1G",
      env: {
        NODE_ENV: "production",
      }
    },
    {
      name: "billing-api",
      script: "src/api_server.py",
      interpreter: "venwin/Scripts/python.exe", // Using the virtual environment's python
      cwd: "c:/billing",
      watch: false,
      autorestart: true,
      max_memory_restart: "1G",
      env: {
        NODE_ENV: "production",
      }
    }
  ]
};
