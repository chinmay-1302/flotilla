# Flotilla Base FAQs - Common Issues and Solutions

This document addresses frequently encountered issues when setting up and running Flotilla federated learning framework. These FAQs are based on real troubleshooting experiences and provide practical solutions.

## Table of Contents

1. [Configuration Issues](#configuration-issues)
2. [Model and Dataset Compatibility](#model-and-dataset-compatibility)
3. [Network and Communication Issues](#network-and-communication-issues)
4. [Training and Runtime Issues](#training-and-runtime-issues)
5. [Visualization and Logging Issues](#visualization-and-logging-issues)
6. [Dependency and Compatibility Issues](#dependency-and-compatibility-issues)

---

## Configuration Issues

### Q1: Why am I getting `KeyError: 'CIFAR10_IID'` during training?

**Problem:** The server cannot find the validation dataset or client cannot find training dataset.

**Common Causes:**

- Incorrect paths in configuration files
- Dataset not properly configured for the selected model
- Running from wrong directory

**Solutions:**

1. **Check Paths in Config Files:**

   ```yaml
   # config/server_config.yaml
   validation_data_dir_path: src/val_data  # NOT ./val_data
   
   # config/client_config.yaml
   dataset_config:
     datasets_dir_path: src/data  # NOT ./data
   ```

2. **Ensure Dataset Compatibility:**

   ```yaml
   # src/data/CIFAR10_IID/train_dataset_config.yaml
   dataset_details:
     suitable_models:
       - CNN
       - MobileNet  # Add your model here
   ```

3. **Run from Project Root:**

   ```bash
   # Correct - run from project root
   cd /path/to/flotilla-revamped
   python src/flo_server.py
   
   # Wrong - don't run from src directory
   cd /path/to/flotilla-revamped/src
   python flo_server.py
   ```

### Q2: Why are my configuration files not being used?

**Problem:** Changes to config files don't seem to take effect.

**Common Causes:**

- Using wrong config file
- Config files not copied to `src/config/`
- Cached configurations

**Solutions:**

1. **Copy Config Files to src/config/:**

   ```bash
   mkdir -p src/config
   cp config/server_config.yaml src/config/
   cp config/client_config.yaml src/config/
   cp config/logger.conf src/config/
   ```

2. **Use Correct Config File:**

   ```bash
   # For training
   python src/flo_session.py config/training_config.yaml --federated_server_endpoint localhost:12345
   
   # For quick setup
   python src/flo_session.py config/flotilla_quicksetup_config.yaml --federated_server_endpoint localhost:12345
   ```

3. **Restart Server and Client** after config changes

### Q3: What's the difference between `training_config.yaml` and `flotilla_quicksetup_config.yaml`?

**Answer:** These serve different purposes:

- **`training_config.yaml`**: Full configuration for custom training setups
- **`flotilla_quicksetup_config.yaml`**: Simplified configuration for quick testing

**Key Differences:**

| Parameter | training_config.yaml | flotilla_quicksetup_config.yaml |
|-----------|---------------------|--------------------------------|
| Purpose | Production/Custom | Quick Testing |
| Model | Configurable | Pre-configured |
| Rounds | Configurable | Usually fewer |
| Plots | Configurable | Often disabled |

**Recommendation:** Use `flotilla_quicksetup_config.yaml` for initial testing, then switch to `training_config.yaml` for production runs.

---

## Model and Dataset Compatibility

### Q4: Why is my model not compatible with my dataset?

**Problem:** Getting errors about model-dataset incompatibility.

**Common Causes:**

- Model expects different input channels (e.g., LeNet5 expects 1 channel, CIFAR10 has 3)
- Model expects different image sizes
- Dataset not listed in model's suitable datasets

**Solutions:**

1. **Check Model Requirements:**

   ```python
   # models/LeNet5/model.py
   self.conv1 = nn.Conv2d(in_channels=1, out_channels=6, kernel_size=5)  # 1 channel
   
   # CIFAR10 has 3 channels - INCOMPATIBLE!
   ```

2. **Check Dataset Configuration:**

   ```yaml
   # models/MobileNet/config.yaml
   model_details:
     suitable_datasets: [CIFAR-10]  # Must match your dataset
   ```

3. **Use Compatible Combinations:**
   - **LeNet5** + **MNIST/FMNIST** (1 channel)
   - **MobileNet** + **CIFAR10** (3 channels)
   - **AlexNet** + **CIFAR10** (3 channels)

### Q5: Why am I getting `AttributeError: 'NoneType' object has no attribute 'loss_function_selection'`?

**Problem:** Loss function or optimizer not loading properly.

**Common Causes:**

- `loss_function_custom` or `optimizer_custom` set to `False`
- Incorrect loss function or optimizer names
- Model class name mismatch

**Solutions:**

1. **Set Custom Flags to True:**

   ```yaml
   client_training_config:
     loss_function_custom: True  # NOT False
     optimizer_custom: True      # NOT False
   ```

2. **Check Model Class Name:**

   ```yaml
   # models/MobileNet/config.yaml
   model_details:
     model_class: MobileNet  # Must match actual class name in model.py
   ```

3. **Verify Loss Function Names:**

   ```yaml
   client_training_config:
     loss_function: crossentropy  # Standard name
     optimizer: adam             # Standard name
   ```

---

## Network and Communication Issues

### Q6: Why am I getting `TimeoutError: [Errno 60] Operation timed out`?

**Problem:** Client cannot determine its IP address.

**Common Causes:**

- Network connectivity issues
- Firewall blocking connections
- Running in restricted environments

**Solutions:**

1. **Check Network Connectivity:**

   ```bash
   ping 8.8.8.8
   ifconfig  # or ip addr on Linux
   ```

2. **Use Fallback IP Detection:**
   The system now includes multiple fallback methods:
   - Local network connection
   - Google DNS with timeout
   - Hostname resolution
   - System commands
   - Default to 127.0.0.1

3. **For Docker/Container Environments:**

   ```bash
   # Set environment variable
   export FEDML_ENV=DOCKER
   ```

### Q7: Why is MQTT communication failing?

**Problem:** Server and client cannot communicate via MQTT.

**Common Causes:**

- MQTT broker not running
- Incorrect MQTT configuration
- paho-mqtt version compatibility

**Solutions:**

1. **Start MQTT Broker:**

   ```bash
   cd docker
   docker-compose up -d
   ```

2. **Check MQTT Configuration:**

   ```yaml
   # config/server_config.yaml
   mqtt:
     mqtt_broker: localhost  # or your broker IP
     mqtt_broker_port: 1883
   ```

3. **Update MQTT Client Code:**

   ```python
   # For paho-mqtt 2.1.0+
   client = mqtt.Client(
       callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
       client_id="your_client_id",
       userdata=user_data,
   )
   ```

---

## Training and Runtime Issues

### Q8: Why is my training session finishing immediately?

**Problem:** Training starts but ends without any rounds.

**Common Causes:**

- Model loading failure
- Dataset not found
- Configuration errors
- Silent exceptions

**Solutions:**

1. **Check Server Logs:**

   ```bash
   tail -f logs/flotilla_*.log
   ```

2. **Enable Debug Logging:**
   Look for these debug messages:

   ```
   About to initialize ServerModelManager with model_dir: models/MobileNet, model_class: MobileNet
   Successfully loaded model class: <class 'model.MobileNet'>
   ```

3. **Verify Model Directory:**

   ```bash
   ls -la models/MobileNet/
   # Should contain: model.py, config.yaml, __init__.py
   ```

4. **Check Dataset Files:**

   ```bash
   ls -la src/data/CIFAR10_IID/
   ls -la src/val_data/CIFAR10_IID/
   ```

### Q9: Why is the round number not incrementing?

**Problem:** Training gets stuck at round 0.

**Common Causes:**

- Aggregation algorithm failure
- Client training timeout
- Model weight transfer issues

**Solutions:**

1. **Check Aggregation Logs:**

   ```
   FINISHED CLIENTS ['client_id']
   AGGREGATED MODEL FROM RESPONSE
   ```

2. **Increase Timeouts:**

   ```yaml
   client_training_config:
     train_timeout_duration_s: 600  # Increase if needed
   
   server_config:
     grpc:
       timeout_s: 600  # Increase if needed
   ```

3. **Check Client Training:**
   Look for client training completion messages in logs.

### Q10: Why am I getting `AioRpcError of RPC that terminated with: status = StatusCode.DEADLINE_EXCEEDED`?

**Problem:** gRPC calls are timing out.

**Common Causes:**

- Client training taking too long
- Network latency
- Insufficient timeout values

**Solutions:**

1. **Increase gRPC Timeout:**

   ```yaml
   # config/server_config.yaml
   grpc:
     timeout_s: 600  # Increase from default 30
   ```

2. **Reduce Training Complexity:**

   ```yaml
   client_training_config:
     epochs: 1        # Reduce from 3
     batch_size: 32   # Increase batch size
   ```

3. **Check Client Performance:**
   Monitor client training time in logs.

---

## Visualization and Logging Issues

### Q11: Why am I getting plotting errors like `ValueError: x and y must have same first dimension`?

**Problem:** Plotting functions crash due to dimension mismatches.

**Common Causes:**

- Hardcoded array lengths
- Missing data points
- Empty log files

**Solutions:**

1. **Check Log File Creation:**

   ```bash
   ls -la logs/
   # Should see log files being created
   ```

2. **Wait for Data:**
   Plotting starts after some training rounds complete.

3. **Check Plot Directory:**

   ```bash
   mkdir -p plots
   ```

### Q12: Why are log files not being created or found?

**Problem:** `FileNotFoundError` for log files.

**Common Causes:**

- Running from wrong directory
- Log directory not created
- Hardcoded paths in code

**Solutions:**

1. **Create Log Directory:**

   ```bash
   mkdir -p logs
   ```

2. **Run from Project Root:**

   ```bash
   cd /path/to/flotilla-revamped
   python src/flo_server.py
   ```

3. **Check Log File Paths:**
   The system now uses relative paths: `logs/flotilla_{session_id}.log`

---

## Dependency and Compatibility Issues

### Q13: Why am I getting PyTorch loading errors?

**Problem:** `_pickle.UnpicklingError: Weights only load failed`

**Common Causes:**

- PyTorch 2.6+ security changes
- Loading datasets with `weights_only=True`

**Solutions:**

1. **Update torch.load Calls:**

   ```python
   # Old (PyTorch < 2.6)
   dataset = torch.load(path).dataset
   
   # New (PyTorch 2.6+)
   dataset = torch.load(path, weights_only=False).dataset
   ```

2. **Check PyTorch Version:**

   ```bash
   python -c "import torch; print(torch.__version__)"
   ```

### Q14: Why is model import failing with `ModuleNotFoundError`?

**Problem:** Python cannot import model classes.

**Common Causes:**

- Incorrect module paths
- Missing `__init__.py` files
- Relative import issues

**Solutions:**

1. **Check Model Directory Structure:**

   ```
   models/MobileNet/
   ├── __init__.py
   ├── model.py
   └── config.yaml
   ```

2. **Use Absolute Paths:**

   ```python
   # Use importlib.util.spec_from_file_location
   spec = importlib.util.spec_from_file_location("model", model_path)
   module = importlib.util.module_from_spec(spec)
   spec.loader.exec_module(module)
   ```

3. **Add to Python Path:**

   ```python
   import sys
   sys.path.append(model_directory)
   ```

### Q15: How do I update dependencies safely?

**Problem:** Dependency updates break existing functionality.

**Solutions:**

1. **Check Compatibility:**
   - paho-mqtt 2.1.0+ requires `callback_api_version`
   - PyTorch 2.6+ requires `weights_only` parameter

2. **Update Gradually:**

   ```bash
   pip install --upgrade paho-mqtt
   pip install --upgrade torch
   ```

3. **Test After Updates:**
   Run a simple training session to verify functionality.

---

## General Troubleshooting Tips

### Debugging Checklist

1. **Check Logs First:** Always start with log files
2. **Verify Paths:** Ensure all paths are correct and relative to project root
3. **Test Components:** Test server, client, and MQTT broker separately
4. **Check Dependencies:** Verify all required packages are installed
5. **Monitor Resources:** Check CPU, memory, and network usage

### Common Commands

```bash
# Check running processes
ps aux | grep python

# Check network connections
netstat -an | grep 12345

# Check MQTT broker
docker ps | grep mqtt

# Monitor logs
tail -f logs/flotilla_*.log

# Check configuration
python -c "import yaml; print(yaml.safe_load(open('config/training_config.yaml')))"
```

### Getting Help

1. Check this FAQ first
2. Review `docs/flotilla_base_changes.md` for specific fixes
3. Check GitHub issues for similar problems
4. Enable debug logging for detailed error information

---

## Quick Reference

### Essential Configuration Files

- `config/training_config.yaml` - Main training configuration
- `config/server_config.yaml` - Server settings
- `config/client_config.yaml` - Client settings
- `models/{MODEL}/config.yaml` - Model-specific settings

### Key Directories

- `src/data/` - Training datasets
- `src/val_data/` - Validation datasets
- `models/` - Model definitions
- `logs/` - Training logs
- `plots/` - Generated plots

### Common Environment Variables

- `FEDML_ENV=DOCKER` - For Docker environments
- `CUDA_VISIBLE_DEVICES` - For GPU control

This FAQ should help you resolve most common issues encountered when setting up and running Flotilla federated learning framework.
