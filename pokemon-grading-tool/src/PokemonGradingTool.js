import React, { useState, useEffect } from "react";
import './App.css';

function PokemonGradingTool() {
  const [cardName, setCardName] = useState("");
  const [cardNumber, setCardNumber] = useState("");
  const [set, setSet] = useState("");
  const [language, setLanguage] = useState("English");
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filterDelta, setFilterDelta] = useState("");
  const [sortCriteria, setSortCriteria] = useState("");
  const [sortOrder, setSortOrder] = useState("asc");

  useEffect(() => {
    console.log("Cards updated:", cards);
  }, [cards]);

  const handleSearch = async () => {
    if (!cardName && !cardNumber) return;
    setLoading(true);

    try {
      const params = new URLSearchParams();

      if (cardName) params.append("searchQuery", cardName.trim());
      if (cardNumber) params.append("searchQuery", cardNumber.trim());
      params.append("language", language);

      const response = await fetch(
        `http://127.0.0.1:8000/api/cards/scrape_and_save/?${params.toString()}`
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      console.log("API Response Data:", data);
      setCards(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error("Error fetching cards:", error);
      setCards([]);
    } finally {
      setLoading(false);
    }
  };

  const filteredCards = (cards || []).filter((card) => {
    if (filterDelta) {
      const deltaValue = parseFloat(card.price_delta || 0);
      if (filterDelta.startsWith(">")) {
        return deltaValue > parseFloat(filterDelta.slice(1));
      } else if (filterDelta.startsWith("<")) {
        return deltaValue < parseFloat(filterDelta.slice(1));
      }
    }
    return true;
  });

  const sortedCards = [...filteredCards].sort((a, b) => {
    if (sortCriteria) {
      const valueA = parseFloat(a[sortCriteria] || 0);
      const valueB = parseFloat(b[sortCriteria] || 0);
      if (sortOrder === "asc") {
        return valueA - valueB;
      } else {
        return valueB - valueA;
      }
    }
    return 0;
  });

  return (
    <div className="container py-5">
      <h1 className="text-center mb-4">Pokemon Grading Tool</h1>
      <div className="mb-4 d-flex justify-content-center align-items-center">
        <input
          type="text"
          value={cardName}
          onChange={(e) => setCardName(e.target.value)}
          placeholder="Enter card name"
          className="form-control me-2"
          style={{ maxWidth: "300px" }}
        />
        <input
          type="text"
          value={cardNumber}
          onChange={(e) => setCardNumber(e.target.value)}
          placeholder="Enter card number"
          className="form-control me-2"
          style={{ maxWidth: "300px" }}
        />
        <input
          type="text"
          value={set}
          onChange={(e) => setSet(e.target.value)}
          placeholder="Enter card set"
          className="form-control me-2"
          style={{ maxWidth: "300px" }}
        />
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          className="form-select me-2"
          style={{ maxWidth: "150px" }}
        >
          <option value="English">English</option>
          <option value="Japanese">Japanese</option>
        </select>
        <button onClick={handleSearch} className="search-btn">
          Search
        </button>
      </div>
      <div className="mb-4 d-flex justify-content-center align-items-center">
        <input
          type="text"
          value={filterDelta}
          onChange={(e) => setFilterDelta(e.target.value)}
          placeholder="Filter by Price Delta (e.g., >500 or <200)"
          className="form-control me-2"
          style={{ maxWidth: "300px" }}
        />
        <select
          value={sortCriteria}
          onChange={(e) => setSortCriteria(e.target.value)}
          className="form-select me-2"
          style={{ maxWidth: "150px" }}
        >
          <option value="">Sort By</option>
          <option value="price_delta">Price Delta</option>
          <option value="profit_potential">Profit Potential</option>
          <option value="rarity">Rarity</option>
        </select>
        <select
          value={sortOrder}
          onChange={(e) => setSortOrder(e.target.value)}
          className="form-select"
          style={{ maxWidth: "150px" }}
        >
          <option value="asc">Ascending</option>
          <option value="desc">Descending</option>
        </select>
      </div>
      {loading ? (
        <div className="text-center">
          <div className="spinner-border text-primary" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
        </div>
      ) : (
        <div className="table-responsive">
          {sortedCards.length > 0 ? (
            <table className="table">
              <thead>
                <tr>
                  <th>Card Name</th>
                  <th>Card Number</th>
                  <th>Set</th>
                  <th>Rarity</th>
                  <th>TCGPlayer Price</th>
                  <th>PSA 10 Price</th>
                  <th>Price Delta</th>
                  <th>Profit Potential</th>
                </tr>
              </thead>
              <tbody>
                {sortedCards.map((card, index) => {
                  const [name, number] = (card.card_name || "").split(" - ");
                  return (
                    <tr key={index}>
                      <td>{name || "Unknown Card"}</td>
                      <td>{number || card.card_number || "N/A"}</td>
                      <td>{card.set_name || "N/A"}</td>
                      <td>{card.rarity || "N/A"}</td>
                      <td>${card.tcgplayer_price || "N/A"}</td>
                      <td>${card.psa_10_price || "N/A"}</td>
                      <td>${card.price_delta || "N/A"}</td>
                      <td>{card.profit_potential || "N/A"}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <p className="text-center">No cards found</p>
          )}
        </div>
      )}
    </div>
  );
}

export default PokemonGradingTool;