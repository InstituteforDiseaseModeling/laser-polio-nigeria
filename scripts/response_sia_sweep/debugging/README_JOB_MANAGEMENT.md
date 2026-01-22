# Response SIA Sweep - Job Management Guide

This guide covers the enhanced job management system for the response-sia-sweep workflow, including automatic cleanup and monitoring capabilities.

## Quick Start

### Current Job Status
```bash
# Quick status check
python3 scripts/response_sia_sweep/core/monitor_jobs.py

# Detailed status with breakdown by response time
python3 scripts/response_sia_sweep/core/monitor_jobs.py --detailed

# Continuous monitoring (updates every 60 seconds)
python3 scripts/response_sia_sweep/core/monitor_jobs.py --continuous
```

### Immediate Cleanup (if needed)
```bash
# See what would be cleaned up (safe)
python3 scripts/response_sia_sweep/core/cleanup_completed_jobs.py --dry-run

# Clean up completed jobs (WARNING: This will delete jobs!)
python3 scripts/response_sia_sweep/core/cleanup_completed_jobs.py
```

## Job Lifecycle Management

### Problem Statement
The original workflow had a critical gap: **completed jobs never shut down automatically**. This leads to:
- Unnecessary resource consumption in the Kubernetes cluster
- Namespace clutter (hundreds of completed job objects)
- Potential memory pressure on the Kubernetes API server

### Solution Overview
We've implemented a 3-tier job management system:

1. **Manual Cleanup**: Immediate cleanup of existing jobs
2. **Enhanced Submission**: New jobs with built-in lifecycle management
3. **Monitoring**: Real-time job status and resource tracking

## Tools

### 1. Manual Cleanup Script
**File**: `scripts/response_sia_sweep/core/cleanup_completed_jobs.py`

Safely removes completed jobs in batches to avoid overwhelming the Kubernetes API.

```bash
# Options
--dry-run              # Show what would be deleted (safe)
--batch-size N         # Jobs per batch (default: 50)
--status STATUS        # Filter by job status (Complete/Failed/Running)
```

**Example Usage**:
```bash
# Safe preview
python3 scripts/response_sia_sweep/core/cleanup_completed_jobs.py --dry-run

# Clean up completed jobs
python3 scripts/response_sia_sweep/core/cleanup_completed_jobs.py

# Clean up failed jobs only
python3 scripts/response_sia_sweep/core/cleanup_completed_jobs.py --status Failed
```

### 2. Enhanced Job Submission
**File**: `scripts/response_sia_sweep/core/submit_sweep_jobs.py`

Improved version of the job submission script with automatic cleanup capabilities.

```bash
# Options
--dry-run                    # Preview without submitting
--cleanup-delay-hours N      # Hours to wait before cleanup (default: 1)
--cleanup-only              # Only run cleanup, don't submit new jobs
--status                    # Show current job status
```

**Key Features**:
- **Automatic pre-cleanup**: Cleans up old jobs before submitting new ones
- **Configurable cleanup delay**: Wait N hours after completion before cleanup
- **Job annotations**: Adds metadata for cleanup tracking
- **Status monitoring**: Built-in status checking

**Example Usage**:
```bash
# Submit jobs with 2-hour cleanup delay
python3 scripts/response_sia_sweep/core/submit_sweep_jobs.py --cleanup-delay-hours 2

# Just clean up old jobs
python3 scripts/response_sia_sweep/core/submit_sweep_jobs.py --cleanup-only

# Preview what would be submitted
python3 scripts/response_sia_sweep/core/submit_sweep_jobs.py --dry-run
```

### 3. Job Monitoring
**File**: `scripts/response_sia_sweep/core/monitor_jobs.py`

Comprehensive monitoring with resource usage tracking and cleanup suggestions.

```bash
# Options
--detailed              # Show response time breakdown
--continuous           # Monitor continuously (Ctrl+C to stop)
--interval N           # Update interval for continuous mode (seconds)
```

**Features**:
- Job status breakdown (Complete/Running/Failed/Pending)
- Resource usage tracking (CPU cores, memory)
- Response time distribution
- Failed job identification
- Cleanup suggestions
- ETA estimation for running jobs

**Example Usage**:
```bash
# One-time detailed report
python3 scripts/response_sia_sweep/core/monitor_jobs.py --detailed

# Real-time monitoring dashboard
python3 scripts/response_sia_sweep/core/monitor_jobs.py --continuous --interval 30
```

## Current Situation Analysis

Based on your current setup:
- **630 completed jobs** have been running for 2+ days
- All jobs show "Complete" status (successful completion)
- Jobs are consuming cluster resources unnecessarily
- No automatic cleanup was configured

## Immediate Recommendations

### 1. Clean Up Existing Jobs (Urgent)
```bash
# Clean up the 630 completed jobs
python3 scripts/response_sia_sweep/core/cleanup_completed_jobs.py
```

### 2. Use Enhanced Workflow Going Forward
Replace the original `submit_sweep_jobs.py` with the enhanced version for future runs:

```bash
# Future job submissions
python3 scripts/response_sia_sweep/core/submit_sweep_jobs.py --cleanup-delay-hours 1
```

### 3. Set Up Monitoring
Monitor active jobs to catch issues early:

```bash
# Set up continuous monitoring in a separate terminal
python3 scripts/response_sia_sweep/core/monitor_jobs.py --continuous
```

## Best Practices

### Job Submission
1. **Always use dry-run first** to preview changes
2. **Set appropriate cleanup delays** (1-24 hours depending on how long you need results)
3. **Monitor resource usage** to avoid cluster overload

### Cleanup Management
1. **Regular cleanup**: Clean up jobs weekly or after collecting results
2. **Batch operations**: Use reasonable batch sizes (50-100 jobs per batch)
3. **Preserve failed jobs**: Don't automatically clean up failed jobs until you investigate

### Monitoring
1. **Check status before large submissions** to ensure cluster capacity
2. **Use continuous monitoring** for long-running sweeps
3. **Set up alerts** for failed jobs (requires additional tooling)

## Resource Management

### Current Scale
- **600 parallel jobs** (6 response times × 100 replicates)
- **Resource requirements per job**: 2 CPU + 8GB memory
- **Total cluster requirements**: 1200 CPU + 4.8TB memory
- **Expected wall-clock time**: 300-450 hours (13-19 days)

### Cluster Limits
Monitor these metrics to avoid overloading:
- Total CPU allocation
- Total memory allocation
- Pod count limits
- Persistent volume usage

## Troubleshooting

### Jobs Stuck in Pending
```bash
# Check cluster resources
kubectl top nodes
kubectl describe nodes

# Check job events
kubectl describe job <job-name>
```

### Cleanup Script Issues
```bash
# Check kubectl connectivity
kubectl get nodes

# Verify job labels
kubectl get jobs -l component=response-sia-sweep --show-labels
```

### Monitoring Not Working
```bash
# Verify label selector
kubectl get jobs -l component=response-sia-sweep

# Check if kubectl top works
kubectl top pods
```

## Migration from Original Workflow

If you're currently using the original workflow:

1. **Clean up existing jobs**:
   ```bash
   python3 scripts/response_sia_sweep/core/cleanup_completed_jobs.py
   ```

2. **Switch to enhanced submission**:
   ```bash
   # Instead of: python scripts/response_sia_sweep/core/submit_sweep_jobs.py
   # Use:
   python3 scripts/response_sia_sweep/core/submit_sweep_jobs.py
   ```

3. **Set up monitoring**:
   ```bash
   python3 scripts/response_sia_sweep/core/monitor_jobs.py --continuous &
   ```

## Future Enhancements

Potential improvements to consider:
- **Kubernetes CronJob** for automatic periodic cleanup
- **Resource quotas** to prevent cluster overload
- **Job templates with TTL** (time-to-live) for automatic cleanup
- **Prometheus monitoring** integration
- **Slack/email alerts** for job failures

---

## Summary

The enhanced job management system addresses the critical gap in the original workflow by providing:
- ✅ **Automatic cleanup** of completed jobs
- ✅ **Real-time monitoring** with resource tracking
- ✅ **Batch management** capabilities
- ✅ **Failure detection** and reporting
- ✅ **Resource usage tracking**

**Most importantly**: Jobs will no longer accumulate indefinitely in your cluster, and you have full visibility into the job lifecycle.
