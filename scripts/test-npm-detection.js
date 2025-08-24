#!/usr/bin/env node

/**
 * Test script to verify npm/npx detection works correctly
 * This helps debug environment issues that cause project creation to fail
 */

const { spawn } = require('child_process');
const os = require('os');
const path = require('path');

console.log('🔍 Testing npm/npx detection...\n');

// Test 1: Check if npm/npx are in PATH
console.log('1. Checking npm/npx availability:');
const isWindows = os.platform() === 'win32';

function testCommand(command) {
  return new Promise((resolve) => {
    const process = spawn(command, ['--version'], {
      stdio: 'pipe',
      shell: isWindows
    });
    
    let output = '';
    process.stdout.on('data', (data) => {
      output += data.toString();
    });
    
    process.on('close', (code) => {
      if (code === 0) {
        console.log(`   ✅ ${command}: ${output.trim()}`);
        resolve(true);
      } else {
        console.log(`   ❌ ${command}: Not found or failed`);
        resolve(false);
      }
    });
    
    process.on('error', () => {
      console.log(`   ❌ ${command}: Not found`);
      resolve(false);
    });
  });
}

async function runTests() {
  const npmAvailable = await testCommand('npm');
  const npxAvailable = await testCommand('npx');
  
  console.log('\n2. Environment information:');
  console.log(`   Platform: ${os.platform()}`);
  console.log(`   Node version: ${process.version}`);
  console.log(`   PATH: ${process.env.PATH?.split(path.delimiter).slice(0, 5).join(', ')}...`);
  
  if (isWindows) {
    console.log('\n3. Windows-specific npm paths:');
    const potentialPaths = [
      path.join(os.homedir(), 'AppData', 'Roaming', 'npm'),
      path.join(os.homedir(), 'AppData', 'Local', 'npm'),
      'C:\\Program Files\\nodejs',
      'C:\\Program Files (x86)\\nodejs'
    ];
    
    const fs = require('fs');
    potentialPaths.forEach(p => {
      const exists = fs.existsSync(p);
      console.log(`   ${exists ? '✅' : '❌'} ${p}`);
    });
  }
  
  console.log('\n4. Test result:');
  if (npmAvailable && npxAvailable) {
    console.log('   ✅ npm and npx are available - project creation should work');
  } else {
    console.log('   ❌ npm or npx not available - this will cause project creation to fail');
    console.log('\n   To fix:');
    console.log('   1. Install Node.js LTS from https://nodejs.org/');
    console.log('   2. Restart your terminal/IDE');
    console.log('   3. Run this test again');
  }
}

runTests().catch(console.error);
