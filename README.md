# KrishiAI - Smart Farming Assistant

A comprehensive farming assistance platform that provides crop recommendations, disease detection, marketplace features, and an AI assistant for farmers.

## Features

- 🌾 Crop Recommendations based on location and conditions
- 🔬 Plant Disease Detection
- 💹 Agricultural Marketplace
- 🤖 AI Farming Assistant
- 📊 Detailed Crop Analysis
- 🗓️ Crop Schedule Management

## Project Structure

```
hackathon/
├── backend/
│   ├── commodity_price.csv    # Commodity price dataset
│   └── main.py               # FastAPI backend server
├── frontend/
│   └── streamlit_app.py      # Streamlit frontend application
├── requirements.txt          # Python dependencies
└── README.md                # Project documentation
```

## Setup Instructions

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/krishiai.git
   cd krishiai
   ```

2. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv venv
   # On Windows
   .\venv\Scripts\activate
   # On Unix or MacOS
   source venv/bin/activate
   ```

3. Upgrade pip to the latest version:
   ```bash
   python -m pip install --upgrade pip
   ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Start the backend server:
   ```bash
   cd backend
   uvicorn main:app --reload
   ```

6. Start the frontend application:
   ```bash
   cd frontend
   streamlit run streamlit_app.py
   ```

## Troubleshooting

If you encounter installation errors:

1. Make sure you have Python 3.8+ installed:
   ```bash
   python --version
   ```

2. Install packages in this specific order:
   ```bash
   pip install --upgrade pip
   pip install wheel setuptools --upgrade
   pip install --only-binary :all: Pillow==11.2.1
   pip install -r requirements.txt
   ```

3. If you still face issues, try installing dependencies one by one:
   ```bash
   pip install numpy==1.21.2
   pip install pandas==1.3.3
   # Then install remaining packages
   ```

## Environment Requirements

- Python 3.8+
- FastAPI
- Streamlit
- Other dependencies listed in requirements.txt

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

This project is licensed under the MIT License
  
## Data Structure

The dataset includes the following information:
- State
- District
- Market
- Commodity
- Variety
- Grade
- Arrival Date
- Minimum Price
- Maximum Price
- Modal Price

## Installation Requirements

1. Python 3.7 or higher
2. Required Python packages:
   ```bash
   pip install pandas
   pip install numpy
   pip install matplotlib
   pip install seaborn
   ```

## How to Use

1. Clone the repository:
   ```bash
   git clone https://github.com/PratikGautam-dev/Hackphaisa
   ```

2. Navigate to the project directory:
   ```bash
   cd agri-price-analysis
   ```

3. Run the analysis scripts:
   ```bash
   python analyze_prices.py
   ```

## Data Analysis Capabilities

1. **Price Trends**
   - Track commodity price variations over time
   - Analyze seasonal price patterns

2. **Market Analysis**
   - Compare prices across different markets
   - Identify price disparities between regions

3. **Commodity Insights**
   - Analyze variety-wise price differences
   - Track grade-based price variations

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE.md file for details

## Contact

Your Name - Pratik Gautam
Project Link: [https://github.com/PratikGautam-dev/Hackphaisa]

## Acknowledgments

- Ministry of Agriculture, Government of India
- National Informatics Centre
- Agricultural Market Information System
- Ministry of Agriculture, Government of India
- National Informatics Centre
- Agricultural Market Information System
