# Claudable Improvement Task List

This document tracks identified improvements and their implementation status.

## 🔧 Critical Issues & Improvements

### **🚨 High Priority (Security & Stability)**

#### 1. Fix Hardcoded Paths and Encryption Key Management
- [x] **Remove hardcoded Windows path in config.py**
  - File: `apps/api/app/core/config.py`
  - Issue: Personal Windows path hardcoded as default
  - Fix: Use relative paths or proper environment detection

- [x] **Improve encryption key management**
  - File: `apps/api/app/core/crypto.py`
  - Issue: Generates random keys in production, making encrypted data unrecoverable
  - Fix: Require explicit encryption keys in production

#### 2. Implement Proper WebSocket Connection Cleanup
- [x] **Add WebSocket connection cleanup**
  - File: `apps/api/app/core/websocket/manager.py`
  - Issue: No cleanup of disconnected WebSocket connections
  - Fix: Implement proper connection cleanup and heartbeat

#### 3. Add Input Validation and Sanitization
- [x] **Add CLI command validation**
  - Files: `apps/api/app/services/cli/unified_manager.py`
  - Issue: Potential command injection in CLI commands
  - Fix: Add input sanitization and validation

- [x] **Add comprehensive input validation module**
  - Files: `apps/api/app/core/validation.py` (new)
  - Issue: Missing comprehensive input validation
  - Fix: Add Pydantic validators and sanitization

#### 4. Replace Deprecated DateTime Usage
- [x] **Update datetime.utcnow() calls**
  - Files: Multiple files throughout codebase
  - Issue: Using deprecated `datetime.utcnow()` (deprecated in Python 3.12+)
  - Fix: Replace with `datetime.now(timezone.utc)`

### **⚡ Medium Priority (Performance & Maintainability)**

#### 5. Memory Leaks and Performance Issues
- [ ] **Fix in-memory settings storage**
  - File: `apps/api/app/api/settings.py`
  - Issue: Settings lost on restart, not scalable
  - Fix: Move to database storage

- [ ] **Optimize process monitoring**
  - File: `apps/api/app/services/local_runtime.py`
  - Issue: Blocking thread-based monitoring for each project
  - Fix: Use async monitoring with proper resource cleanup

#### 6. Error Handling Improvements
- [ ] **Implement specific exception types**
  - Files: Multiple API files
  - Issue: Generic exception handling exposes internal errors
  - Fix: Create custom exception classes with user-friendly messages

- [ ] **Add comprehensive error logging**
  - Files: Throughout codebase
  - Issue: Basic logging with print statements
  - Fix: Implement structured logging with proper levels

#### 7. Code Quality Issues
- [x] **Complete TODO implementations**
  - Files: `apps/api/app/api/projects/preview.py`, `apps/web/components/settings/GeneralSettings.tsx`
  - Issue: Multiple unfinished features
  - Fix: Complete or remove TODO items

- [x] **Standardize code comments**
  - Files: Multiple files with Korean comments
  - Issue: Mixed language comments
  - Fix: Standardize to English for international collaboration

### **🏗️ Low Priority (Architecture & Features)**

#### 8. Architecture Improvements
- [x] **Reduce tight coupling**
  - Issue: CLI managers directly import WebSocket managers
  - Fix: Implement proper dependency injection

- [x] **Add service layer abstractions**
  - Issue: No interface/protocol definitions for CLI adapters
  - Fix: Create proper abstractions and interfaces

#### 9. Configuration Management
- [ ] **Fix environment variable inconsistencies**
  - Issue: Different default values across files
  - Fix: Centralize configuration with validation

- [ ] **Add configuration validation**
  - Issue: No validation of required environment variables
  - Fix: Implement configuration schema and type checking

#### 10. Testing & Monitoring
- [ ] **Add test coverage**
  - Issue: No unit tests found in codebase
  - Fix: Implement comprehensive test suite

- [ ] **Implement proper observability**
  - Issue: Limited monitoring and metrics
  - Fix: Add metrics collection and health checks

## 📊 Progress Tracking

### Completed Tasks
- [x] Windows compatibility fixes for CLI execution
- [x] Path separator handling improvements
- [x] Claude hook script Windows support
- [x] **HIGH PRIORITY SECURITY & STABILITY IMPROVEMENTS**
  - [x] Fixed hardcoded paths and encryption key management
  - [x] Implemented proper WebSocket connection cleanup with heartbeat
  - [x] Added comprehensive input validation and sanitization
  - [x] Replaced all deprecated datetime.utcnow() usage
- [x] **CODE QUALITY IMPROVEMENTS**
  - [x] Completed TODO implementations (preview port storage, settings save logic)
  - [x] Standardized all Korean comments to English
- [x] **ARCHITECTURE IMPROVEMENTS**
  - [x] Implemented proper dependency injection system
  - [x] Reduced tight coupling between CLI managers and WebSocket managers
  - [x] Created service layer abstractions with protocols and interfaces

### In Progress
- [ ] Medium priority performance improvements

### Next Up
- [ ] Medium priority performance improvements
- [ ] Architecture refactoring
- [ ] Test coverage implementation

## 🎯 Implementation Notes

### Security Considerations
- All encryption keys must be explicitly provided in production
- Input validation should be comprehensive and fail-safe
- WebSocket connections need proper authentication and rate limiting

### Performance Targets
- WebSocket connections should auto-cleanup within 30 seconds of disconnect
- Process monitoring should use async patterns to avoid blocking
- Database queries should be optimized with proper indexing

### Code Quality Standards
- All new code should include comprehensive error handling
- Comments and documentation should be in English
- TODO items should have associated GitHub issues or be removed

---

**Last Updated**: 2025-01-27
**Total Tasks**: 20
**Completed**: 11 (including all high-priority security & stability improvements + code quality + architecture)
**Remaining**: 9
