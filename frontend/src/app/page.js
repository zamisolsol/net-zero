// app/page.js
"use client";

import React, { useState } from 'react';
import WelcomeScreen from '../../components/Welcomescreen';
import ProductPhotoAnalyzer from '../../components/ProductPhotoAnalyzer';
import EnvironmentReport from '../../components/EnvironmentReport';


export default function HomePage() {
  const [currentScreen, setCurrentScreen] = useState('welcome');

  const handleStartScan = () => {
    setCurrentScreen('scan');
  };

  const handleEnvironmentReport = () => {
    setCurrentScreen('report');
  };

  const handleBackToWelcome = () => {
    setCurrentScreen('welcome');
  };

  const renderCurrentScreen = () => {
    switch (currentScreen) {
      case 'welcome':
        return (
          <WelcomeScreen 
            onStartScan={handleStartScan}
            onEnvironmentReport={handleEnvironmentReport}
          />
        );
      
      case 'scan':
        return (
          <ProductPhotoAnalyzer 
            onBack={handleBackToWelcome}
          />
        );
      
      case 'report':
        return (
          <EnvironmentReport 
            onBack={handleBackToWelcome}
          />
        );
      
      default:
        return (
          <WelcomeScreen 
            onStartScan={handleStartScan}
            onEnvironmentReport={handleEnvironmentReport}
          />
        );
    }
  };

  return renderCurrentScreen();
}