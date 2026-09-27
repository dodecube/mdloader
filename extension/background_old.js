let downloadTimeout = null;
let downloadPort = null;
let downloadQueue = [];
let isDownloading = false;

// Handle extension icon click
chrome.action.onClicked.addListener(async (tab) => {
  try {
    console.log('Extension icon clicked on tab:', tab.url);
    
    // Add to queue
    const jobId = Date.now().toString();
    const downloadJob = {
      id: jobId,
      url: tab.url,
      tabId: tab.id,
      status: 'queued',
      addedAt: new Date()
    };
    
    downloadQueue.push(downloadJob);
    updateQueueBadge();
    
    showNotification('Download added to queue', 'info', tab.id);
    console.log(`Added to queue. Queue length: ${downloadQueue.length}`);
    
    // Start processing queue if not already downloading
    if (!isDownloading) {
      processNextDownload();
    }
    
  } catch (error) {
    console.error('Error adding to queue:', error);
    showNotification('Failed to add to queue: ' + error.message, 'error', tab.id);
  }
});

// Process next download in queue
async function processNextDownload() {
  if (downloadQueue.length === 0) {
    isDownloading = false;
    updateQueueBadge();
    return;
  }
  
  const nextJob = downloadQueue.find(job => job.status === 'queued');
  if (!nextJob) {
    isDownloading = false;
    updateQueueBadge();
    return;
  }
  
  isDownloading = true;
  nextJob.status = 'downloading';
  nextJob.startedAt = new Date();
  
  updateQueueBadge();
  await startDownload(nextJob);
}

// Modified startDownload to work with queue jobs
async function startDownload(job) {
  try {
    console.log('Starting download for URL:', job.url);
    
    // Show initial notification
    showNotification('Starting download...', 'info', job.tabId);
    
    // Update badge for current download
    chrome.action.setBadgeText({ text: '...' });
    chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });
    
    // Set timeout for download process
    downloadTimeout = setTimeout(() => {
      if (downloadPort) {
        downloadPort.disconnect();
        downloadPort = null;
      }
      handleDownloadError('Download timed out. Please try again.', job);
    }, 300000); // 5 minutes timeout
    
    // Connect to native application
    try {
      downloadPort = chrome.runtime.connectNative('com.example.youtube_downloader');
      console.log('Connected to native host');
    } catch (error) {
      throw new Error('Cannot connect to native host. Make sure it is installed and configured properly.');
    }
    
    // Set up message listener
    downloadPort.onMessage.addListener((response) => {
      console.log('Received message from native host:', response);
      handleDownloadResponse(response, job);
    });
    
    // Set up disconnect handler
    downloadPort.onDisconnect.addListener(() => {
      console.log('Disconnected from native host');
      handleDownloadDisconnect(job);
    });
    
    // Send download request
    console.log('Sending download request for URL:', job.url);
    downloadPort.postMessage({
      action: 'download',
      url: job.url
    });
    
  } catch (error) {
    console.error('Error in startDownload:', error);
    handleDownloadError('Failed to start download: ' + error.message, job);
  }
}

// Modified response handler for queue support
function handleDownloadResponse(response, job) {
  console.log('Processing response for job:', job.id, response);
  
  // Reset timeout on any activity
  if (downloadTimeout) {
    clearTimeout(downloadTimeout);
    downloadTimeout = setTimeout(() => {
      handleDownloadError('Download timed out. Please try again.', job);
    }, 300000);
  }
  
  if (response && response.status) {
    if (response.status === 'progress') {
      // Update progress
      console.log('Progress update:', response.progress, response.message);
      
      // Update badge with progress
      if (response.progress !== undefined) {
        const progressText = response.progress === 100 ? '✓' : `${response.progress}%`;
        chrome.action.setBadgeText({ text: progressText });
      }
      
      showNotification(response.message, 'info', job.tabId, response.progress);
      
    } else if (response.status === 'success') {
      handleDownloadSuccess(job);
    } else if (response.status === 'error') {
      handleDownloadError('Download failed: ' + response.message, job);
    }
  } else {
    console.warn('Invalid response format:', response);
    handleDownloadError('Invalid response from downloader', job);
  }
}

// Modified success handler for queue support
function handleDownloadSuccess(job) {
  console.log('Download completed successfully for job:', job.id);
  
  // Clear timeout
  if (downloadTimeout) {
    clearTimeout(downloadTimeout);
    downloadTimeout = null;
  }
  
  // Update job status
  job.status = 'completed';
  job.completedAt = new Date();
  
  // Remove completed job from queue
  downloadQueue = downloadQueue.filter(item => item.id !== job.id);
  
  // Update badge to show success
  chrome.action.setBadgeText({ text: '✓' });
  chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });
  
  showNotification('Download completed successfully!', 'success', job.tabId);
  
  // Clear badge after 3 seconds and process next download
  setTimeout(() => {
    chrome.action.setBadgeText({ text: '' });
    
    // Disconnect from port
    if (downloadPort) {
      downloadPort.disconnect();
      downloadPort = null;
    }
    
    // Process next download
    processNextDownload();
  }, 3000);
}

// Modified error handler for queue support
function handleDownloadError(errorMessage, job) {
  console.error('Download error for job:', job.id, errorMessage);
  
  // Clear timeout
  if (downloadTimeout) {
    clearTimeout(downloadTimeout);
    downloadTimeout = null;
  }
  
  // Update job status
  job.status = 'error';
  job.error = errorMessage;
  job.failedAt = new Date();
  
  // Update badge to show error
  chrome.action.setBadgeText({ text: '!' });
  chrome.action.setBadgeBackgroundColor({ color: '#FF0000' });
  
  showNotification(errorMessage, 'error', job.tabId);
  
  // Clear badge after 5 seconds and process next download
  setTimeout(() => {
    chrome.action.setBadgeText({ text: '' });
    
    // Disconnect from port
    if (downloadPort) {
      downloadPort.disconnect();
      downloadPort = null;
    }
    
    // Process next download (error doesn't remove from queue, user can retry)
    processNextDownload();
  }, 5000);
}

// Modified disconnect handler for queue support
function handleDownloadDisconnect(job) {
  console.log('Handle download disconnect for job:', job.id);
  
  // Clear timeout
  if (downloadTimeout) {
    clearTimeout(downloadTimeout);
    downloadTimeout = null;
  }
  
  // Only show error if we didn't complete successfully
  const wasSuccess = downloadPort && downloadPort.lastMessage && 
                    downloadPort.lastMessage.status === 'success';
  
  if (!wasSuccess) {
    job.status = 'error';
    job.error = 'Download connection lost';
    job.failedAt = new Date();
    showNotification('Download connection lost', 'error', job.tabId);
  }
  
  downloadPort = null;
  
  // Process next download
  if (!wasSuccess) {
    setTimeout(() => {
      processNextDownload();
    }, 2000);
  }
}

// Update badge to show queue status
function updateQueueBadge() {
  const downloadingCount = downloadQueue.filter(job => job.status === 'downloading').length;
  const queuedCount = downloadQueue.filter(job => job.status === 'queued').length;
  
  if (downloadingCount > 0 && queuedCount > 0) {
    // Show both current download and queue count
    chrome.action.setBadgeText({ text: `1+${queuedCount}` });
    chrome.action.setBadgeBackgroundColor({ color: '#FF9800' });
  } else if (queuedCount > 0) {
    // Show only queue count
    chrome.action.setBadgeText({ text: queuedCount.toString() });
    chrome.action.setBadgeBackgroundColor({ color: '#FF9800' });
  } else if (downloadingCount > 0) {
    // Download in progress but no queue
    chrome.action.setBadgeText({ text: '...' });
    chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });
  } else {
    // No active downloads
    chrome.action.setBadgeText({ text: '' });
  }
}

// Add context menu for queue management
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'showQueue',
    title: 'Show Download Queue',
    contexts: ['action']
  });
  
  chrome.contextMenus.create({
    id: 'clearQueue',
    title: 'Clear Download Queue',
    contexts: ['action']
  });
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === 'showQueue') {
    showQueueStatus(tab.id);
  } else if (info.menuItemId === 'clearQueue') {
    clearQueue(tab.id);
  }
});

// Show current queue status
function showQueueStatus(tabId) {
  const downloading = downloadQueue.filter(job => job.status === 'downloading');
  const queued = downloadQueue.filter(job => job.status === 'queued');
  const completed = downloadQueue.filter(job => job.status === 'completed');
  const errors = downloadQueue.filter(job => job.status === 'error');
  
  let message = `Download Queue Status:\n\n`;
  message += `Downloading: ${downloading.length}\n`;
  message += `Queued: ${queued.length}\n`;
  message += `Completed: ${completed.length}\n`;
  message += `Errors: ${errors.length}\n\n`;
  
  if (queued.length > 0) {
    message += `Next in queue:\n`;
    queued.slice(0, 3).forEach((job, index) => {
      const url = job.url.length > 50 ? job.url.substring(0, 50) + '...' : job.url;
      message += `${index + 1}. ${url}\n`;
    });
    if (queued.length > 3) {
      message += `... and ${queued.length - 3} more`;
    }
  }
  
  showNotification(message, 'info', tabId);
}

// Clear the download queue
function clearQueue(tabId) {
  const wasDownloading = isDownloading;
  const queueSize = downloadQueue.length;
  
  // Keep only currently downloading job
  const currentlyDownloading = downloadQueue.find(job => job.status === 'downloading');
  downloadQueue = currentlyDownloading ? [currentlyDownloading] : [];
  
  updateQueueBadge();
  
  if (queueSize > 0) {
    showNotification(`Cleared ${wasDownloading ? queueSize - 1 : queueSize} items from queue`, 'info', tabId);
  } else {
    showNotification('Queue is already empty', 'info', tabId);
  }
}

// Existing showNotification function remains the same
function showNotification(message, type, tabId, progress = null) {
  const notificationOptions = {
    type: 'basic',
    iconUrl: 'icons/icon48.png',
    title: 'URL Downloader',
    message: message,
    priority: 1
  };
  
  // Set different icons based on notification type
  switch (type) {
    case 'success':
      notificationOptions.title = 'Download Complete';
      break;
    case 'error':
      notificationOptions.title = 'Download Error';
      notificationOptions.priority = 2;
      break;
    case 'info':
    default:
      notificationOptions.title = 'Download Progress';
      if (progress !== null) {
        notificationOptions.message = `(${progress}%) ${message}`;
      }
  }
  
  // Create notification
  chrome.notifications.create({
    type: 'basic',
    ...notificationOptions
  });
  
  // Also log to console for debugging
  console.log(`Notification [${type}]:`, message);
}

// Clean up when extension is unloaded
chrome.runtime.onSuspend.addListener(() => {
  if (downloadTimeout) {
    clearTimeout(downloadTimeout);
  }
  if (downloadPort) {
    downloadPort.disconnect();
  }
});