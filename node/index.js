const noble = require("@abandonware/noble");
const fs = require("fs");
const path = require("path");

// Create logs directory if it doesn't exist
const logsDir = path.join(__dirname, "logs");
if (!fs.existsSync(logsDir)) {
  fs.mkdirSync(logsDir);
}

// Create log file with timestamp
const logFileName = `ble_scan_${new Date()
  .toISOString()
  .replace(/[:.]/g, "-")}.json`;
const logFilePath = path.join(logsDir, logFileName);

console.log(`📝 Logging to: ${logFilePath}`);

function getISOTimestamp() {
  return new Date().toISOString();
}

function getHumanTimestamp() {
  const now = new Date();
  return now.toLocaleString("en-US", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    fractionalSecondDigits: 3,
    hour12: false,
  });
}

function logAdvertisement(advertisementData) {
  // Append to JSON log file for replay
  const logEntry = JSON.stringify(advertisementData) + "\n";
  fs.appendFileSync(logFilePath, logEntry);
}

// Bluetooth Company Identifier codes (first 2 bytes of manufacturer data)
// Source: https://www.bluetooth.com/specifications/assigned-numbers/company-identifiers/
const COMPANY_IDENTIFIERS = {
  0x004c: "Apple, Inc.",
  0x0006: "Microsoft",
  0x00e0: "Google",
  0x0075: "Samsung Electronics Co. Ltd.",
  0x000f: "Broadcom Corporation",
  0x0001: "Nokia Mobile Phones",
  0x000a: "Qualcomm",
  0x0059: "Nordic Semiconductor ASA",
  0x0087: "Garmin International, Inc.",
  0x006f: "Amazon.com Services, Inc.",
  0x0171: "Fitbit, Inc.",
  0x0224: "Twitter, Inc.",
  0x0700: "Shenzhen Jingxun Software Telecommunication Technology Co., Ltd.", // Common for fitness devices
  0x70a8: "Unknown/Generic Fitness Device", // Custom identifier seen in WalkingPad devices
  0xa806: "Matter/Thread Device",
  // Add more as needed
};

function getManufacturerName(manufacturerData) {
  if (!manufacturerData || manufacturerData.length < 2) {
    return "Unknown";
  }

  // Company identifier is in little-endian format (first 2 bytes)
  const companyId = manufacturerData.readUInt16LE(0);
  const companyName = COMPANY_IDENTIFIERS[companyId];

  if (companyName) {
    return `${companyName} (0x${companyId
      .toString(16)
      .toUpperCase()
      .padStart(4, "0")})`;
  } else {
    return `Unknown Company (0x${companyId
      .toString(16)
      .toUpperCase()
      .padStart(4, "0")})`;
  }
}

function parseManufacturerData(manufacturerData) {
  if (!manufacturerData || manufacturerData.length < 2) {
    return { companyName: "Unknown", rawData: "" };
  }

  const companyId = manufacturerData.readUInt16LE(0);
  const companyName = getManufacturerName(manufacturerData);
  const remainingData = manufacturerData.slice(2);

  return {
    companyId: `0x${companyId.toString(16).toUpperCase().padStart(4, "0")}`,
    companyName,
    rawData: manufacturerData.toString("hex"),
    payloadData: remainingData.toString("hex"),
    payloadLength: remainingData.length,
  };
}

console.log("Starting Bluetooth advertisement scanner...");

// Event handler for when the adapter state changes
noble.on("stateChange", (state) => {
  console.log(`Bluetooth adapter state: ${state}`);

  if (state === "poweredOn") {
    console.log("Starting scan for BLE advertisements...");
    // Start scanning for all devices (no service filter)
    noble.startScanning([], true); // true = allow duplicates
  } else {
    console.log("Bluetooth not ready. Ensure Bluetooth is enabled.");
    noble.stopScanning();
  }
});

// Event handler for discovered devices
noble.on("discover", (peripheral) => {
  const timestamp = getISOTimestamp();
  const humanTime = getHumanTimestamp();
  const advertisement = peripheral.advertisement;
  const rssi = peripheral.rssi;
  const address = peripheral.address || "Unknown";
  const addressType = peripheral.addressType || "Unknown";

  // FILTERING OPTIONS - Uncomment the ones you want to use:

  // 1. Filter by device name (case-insensitive partial match)
  const targetDeviceName = "KS-REMOTE-01"; // "WalkingPad"; // Change this to your target device
  if (targetDeviceName) {
    if (
      !(advertisement.localName || "")
        .toLowerCase()
        .includes(targetDeviceName.toLowerCase())
    ) {
      return; // Skip this device
    }
  }

  // Create comprehensive advertisement data for replay
  const advertisementData = {
    timestamp: timestamp,
    humanTime: humanTime,
    scanType: "discovery",
    peripheral: {
      id: peripheral.id,
      uuid: peripheral.uuid,
      address: address,
      addressType: addressType,
      connectable: peripheral.connectable,
      rssi: rssi,
      state: peripheral.state,
    },
    advertisement: {
      localName: advertisement.localName || null,
      serviceUuids: advertisement.serviceUuids || [],
      serviceData: advertisement.serviceData
        ? advertisement.serviceData.map((data) => ({
            uuid: data.uuid,
            data: data.data.toString("hex"),
          }))
        : [],
      manufacturerData: advertisement.manufacturerData
        ? advertisement.manufacturerData.toString("hex")
        : null,
      txPowerLevel: advertisement.txPowerLevel,
      flags: advertisement.flags,
      solicitationServiceUuids: advertisement.solicitationServiceUuids || [],
    },
  };

  // Add manufacturer information if available
  if (advertisement.manufacturerData) {
    const manufacturerInfo = parseManufacturerData(
      advertisement.manufacturerData
    );
    advertisementData.manufacturer = {
      companyId: manufacturerInfo.companyId,
      companyName: manufacturerInfo.companyName,
      rawData: manufacturerInfo.rawData,
      payloadData: manufacturerInfo.payloadData,
      payloadLength: manufacturerInfo.payloadLength,
    };
  }

  // Log to file for replay
  logAdvertisement(advertisementData);

  // Human-readable console output
  console.log(`\n🕐 [${humanTime}] --- Bluetooth Advertisement Detected ---`);
  console.log(`📍 Device Address: ${address} (${addressType})`);
  console.log(`📶 RSSI: ${rssi} dBm`);
  console.log(`🔗 Connectable: ${peripheral.connectable}`);
  console.log(`🆔 Peripheral ID: ${peripheral.id}`);

  // Log device name if available
  if (advertisement.localName) {
    console.log(`📛 Local Name: ${advertisement.localName}`);
  }

  // Log manufacturer data if available
  if (advertisement.manufacturerData) {
    const manufacturerInfo = parseManufacturerData(
      advertisement.manufacturerData
    );
    console.log(`🏭 Manufacturer: ${manufacturerInfo.companyName}`);
    console.log(`🔢 Manufacturer ID: ${manufacturerInfo.companyId}`);
    console.log(`📊 Manufacturer Data: ${manufacturerInfo.rawData}`);
    if (manufacturerInfo.payloadLength > 0) {
      console.log(
        `💾 Payload Data: ${manufacturerInfo.payloadData} (${manufacturerInfo.payloadLength} bytes)`
      );
    }
  }

  // Log service UUIDs if available
  if (advertisement.serviceUuids && advertisement.serviceUuids.length > 0) {
    console.log(`🔧 Service UUIDs: ${advertisement.serviceUuids.join(", ")}`);
  }

  // Log service data if available
  if (advertisement.serviceData && advertisement.serviceData.length > 0) {
    console.log("📋 Service Data:");
    advertisement.serviceData.forEach((data) => {
      console.log(`    UUID: ${data.uuid}, Data: ${data.data.toString("hex")}`);
    });
  }

  // Log TX power level if available
  if (advertisement.txPowerLevel !== undefined) {
    console.log(`📡 TX Power Level: ${advertisement.txPowerLevel} dBm`);
  }

  // Log flags if available
  if (advertisement.flags !== undefined) {
    console.log(
      `🏁 Flags: 0x${advertisement.flags.toString(16).padStart(2, "0")}`
    );
  }

  // Replay command
  console.log(`\n🔄 REPLAY DATA (JSON):`);
  console.log(JSON.stringify(advertisementData, null, 2));
  console.log("----------------------------------------");
});

// Event handler for scan start
noble.on("scanStart", () => {
  const startTime = getHumanTimestamp();
  console.log(`🔍 [${startTime}] BLE scan started successfully`);

  // Log scan start event
  const scanStartEvent = {
    timestamp: getISOTimestamp(),
    humanTime: startTime,
    scanType: "scanStart",
    event: "Bluetooth scan started",
  };
  logAdvertisement(scanStartEvent);
});

// Event handler for scan stop
noble.on("scanStop", () => {
  const stopTime = getHumanTimestamp();
  console.log(`⏹️  [${stopTime}] BLE scan stopped`);

  // Log scan stop event
  const scanStopEvent = {
    timestamp: getISOTimestamp(),
    humanTime: stopTime,
    scanType: "scanStop",
    event: "Bluetooth scan stopped",
  };
  logAdvertisement(scanStopEvent);

  console.log(`\n📄 Complete log saved to: ${logFilePath}`);
  console.log(
    `💡 To replay advertisements, use the JSON data from the log file`
  );
});

// Error handling
noble.on("error", (error) => {
  console.error("Noble error:", error);
});

// Graceful shutdown handling
process.on("SIGINT", () => {
  console.log("\nShutting down gracefully...");
  noble.stopScanning();
  process.exit(0);
});

process.on("SIGTERM", () => {
  console.log("\nShutting down gracefully...");
  noble.stopScanning();
  process.exit(0);
});

console.log("Bluetooth scanner initialized. Press Ctrl+C to stop.");
