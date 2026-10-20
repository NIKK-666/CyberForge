# DELIBERATELY VULNERABLE demo workflow: runs PR code with secrets and a write token.
name: CI
on:
  pull_request_target:
    branches: [main]
permissions: write-all
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
      - name: Start local listener (demo only)
        run: |
          nohup python3 demo/listener.py > /dev/null 2>&1 &
          sleep 1
      - name: Install dependencies
        run: npm install
        env:
          FAKE_SECRET: ${{ secrets.FAKE_SECRET }}
      - name: Show what the attacker listener received
        if: always()
        run: |
          sleep 1
          cat listener.log || echo "listener received nothing"
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
      - run: npm install --ignore-scripts
