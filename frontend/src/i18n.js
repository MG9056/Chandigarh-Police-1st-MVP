import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

// the translations
const resources = {
  en: {
    translation: {
      "Welcome to DarKnight": "Welcome to DarKnight",
      "Dashboard": "Dashboard",
      "Data Collection Status": "Data Collection Status",
      "Alerts & Suspicious Activity": "Alerts & Suspicious Activity",
      "Alerts": "Alerts",
      "Network Visualization": "Network Visualization",
      "Search & Investigation": "Search & Investigation",
      "Reports & Evidence": "Reports & Evidence",
      "Security & Access Control": "Security & Access Control",
      "Settings": "Settings",
      "General Info": "General Info",
      "Details": "Details",
      "Further Details": "Further Details",
      "Active Investigations": "Active Investigations",
      "Critical Alerts": "Critical Alerts",
      "Sources Monitored": "Sources Monitored",
      "Entity Correlation & Network Visualization": "Entity Correlation & Network Visualization",
      "Automated Alert Generation": "Automated Alert Generation",
      "Suspicious Activity Detection": "Suspicious Activity Detection",
      "Search & Investigation Support": "Search & Investigation Support",
      "dashboard": {
        "detailsDescription": "Select an item from the General Info panel to view detailed metrics, suspect relationships, or actionable intelligence here. The dashboard automatically aggregates signals across multiple encrypted channels."
      }
    }
  },
  hi: {
    translation: {
      "Welcome to DarKnight": "DarKnight में आपका स्वागत है",
      "Dashboard": "डैशबोर्ड",
      "Data Collection Status": "डेटा संग्रह स्थिति",
      "Alerts & Suspicious Activity": "अलर्ट और संदिग्ध गतिविधि",
      "Alerts": "अलर्ट",
      "Network Visualization": "नेटवर्क विज़ुअलाइज़ेशन",
      "Search & Investigation": "खोज और जांच",
      "Reports & Evidence": "रिपोर्ट और साक्ष्य",
      "Security & Access Control": "सुरक्षा और पहुंच नियंत्रण",
      "Settings": "सेटिंग्स",
      "General Info": "सामान्य जानकारी",
      "Details": "विवरण",
      "Further Details": "अधिक विवरण",
      "Active Investigations": "सक्रिय जांच",
      "Critical Alerts": "गंभीर अलर्ट",
      "Sources Monitored": "निगरानी किए गए स्रोत",
      "Entity Correlation & Network Visualization": "एंटिटी सहसंबंध और नेटवर्क विज़ुअलाइज़ेशन",
      "Automated Alert Generation": "स्वचालित अलर्ट जेनरेशन",
      "Suspicious Activity Detection": "संदिग्ध गतिविधि का पता लगाना",
      "Search & Investigation Support": "खोज और जांच सहायता",
      "dashboard": {
      "detailsDescription": "विस्तृत मेट्रिक्स, संदिग्ध संबंधों या कार्रवाई योग्य जानकारी देखने के लिए सामान्य जानकारी पैनल से किसी आइटम का चयन करें। डैशबोर्ड स्वचालित रूप से कई एन्क्रिप्टेड चैनलों से संकेतों को एकत्र करता है।"
      }
    }
  },
  pa: {
    translation: {
      "Welcome to DarKnight": "DarKnight ਵਿੱਚ ਤੁਹਾਡਾ ਸਵਾਗਤ ਹੈ",
      "Dashboard": "ਡੈਸ਼ਬੋਰਡ",
      "Data Collection Status": "ਡਾਟਾ ਇਕੱਤਰ ਕਰਨ ਦੀ ਸਥਿਤੀ",
      "Alerts & Suspicious Activity": "ਚੇਤਾਵਨੀਆਂ ਅਤੇ ਸ਼ੱਕੀ ਗਤੀਵਿਧੀ",
      "Alerts": "ਚੇਤਾਵਨੀਆਂ",
      "Network Visualization": "ਨੈੱਟਵਰਕ ਵਿਜ਼ੂਅਲਾਈਜ਼ੇਸ਼ਨ",
      "Search & Investigation": "ਖੋਜ ਅਤੇ ਪੜਤਾਲ",
      "Reports & Evidence": "ਰਿਪੋਰਟਾਂ ਅਤੇ ਸਬੂਤ",
      "Security & Access Control": "ਸੁਰੱਖਿਆ ਅਤੇ ਪਹੁੰਚ ਨਿਯੰਤਰਣ",
      "Settings": "ਸੈਟਿੰਗਾਂ",
      "General Info": "ਆਮ ਜਾਣਕਾਰੀ",
      "Details": "ਵੇਰਵੇ",
      "Further Details": "ਹੋਰ ਵੇਰਵੇ",
      "Active Investigations": "ਸਰਗਰਮ ਪੜਤਾਲਾਂ",
      "Critical Alerts": "ਗੰਭੀਰ ਚੇਤਾਵਨੀਆਂ",
      "Sources Monitored": "ਨਿਗਰਾਨੀ ਕੀਤੇ ਸਰੋਤ",
      "Entity Correlation & Network Visualization": "ਇਕਾਈ ਸਹਿਸੰਬੰਧ ਅਤੇ ਨੈੱਟਵਰਕ ਵਿਜ਼ੂਅਲਾਈਜ਼ੇਸ਼ਨ",
      "Automated Alert Generation": "ਸਵੈਚਲਿਤ ਚੇਤਾਵਨੀ ਉਤਪਤੀ",
      "Suspicious Activity Detection": "ਸ਼ੱਕੀ ਗਤੀਵਿਧੀ ਦੀ ਪਛਾਣ",
      "Search & Investigation Support": "ਖੋਜ ਅਤੇ ਪੜਤਾਲ ਸਹਾਇਤਾ",
      "dashboard": {
      "detailsDescription": "ਵਿਸਤ੍ਰਿਤ ਮੈਟ੍ਰਿਕਸ, ਸ਼ੱਕੀ ਸੰਬੰਧਾਂ ਜਾਂ ਕਾਰਵਾਈਯੋਗ ਜਾਣਕਾਰੀ ਨੂੰ ਦੇਖਣ ਲਈ ਆਮ ਜਾਣਕਾਰੀ ਪੈਨਲ ਵਿੱਚੋਂ ਇੱਕ ਆਈਟਮ ਚੁਣੋ। ਡੈਸ਼ਬੋਰਡ ਆਪਣੇ ਆਪ ਕਈ ਐਨਕ੍ਰਿਪਟ ਕੀਤੇ ਚੈਨਲਾਂ ਤੋਂ ਸੰਕੇਤ ਇਕੱਠੇ ਕਰਦਾ ਹੈ।"
      }
    }
  }
};

i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: "en", // default language
    fallbackLng: "en",
    interpolation: {
      escapeValue: false
    }
  });

export default i18n;
