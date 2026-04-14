/**
 * Primary work areas for delivery partners.
 * Live OpenWeather + WAQI use `lat` / `lon`; `id` drives risk features & fraud zone match.
 */
export type WorkZone = {
  id: string;
  label: string;
  lat: number;
  lon: number;
};

export const WORK_ZONES: WorkZone[] = [
  { id: "chennai-t-nagar", label: "Chennai — T. Nagar", lat: 13.0418, lon: 80.2341 },
  { id: "chennai-velachery", label: "Chennai — Velachery", lat: 12.9815, lon: 80.2209 },
  { id: "chennai-omr", label: "Chennai — OMR / Sholinganallur", lat: 12.9499, lon: 80.2381 },
  { id: "bengaluru-koramangala", label: "Bengaluru — Koramangala", lat: 12.9352, lon: 77.6245 },
  { id: "bengaluru-whitefield", label: "Bengaluru — Whitefield", lat: 12.9698, lon: 77.75 },
  { id: "bengaluru-indiranagar", label: "Bengaluru — Indiranagar", lat: 12.9719, lon: 77.6412 },
  { id: "bengaluru-electronic-city", label: "Bengaluru — Electronic City", lat: 12.8456, lon: 77.6603 },
  { id: "mumbai-andheri", label: "Mumbai — Andheri", lat: 19.1136, lon: 72.8697 },
  { id: "mumbai-borivali", label: "Mumbai — Borivali", lat: 19.2313, lon: 72.8564 },
  { id: "mumbai-thane", label: "Mumbai — Thane", lat: 19.2183, lon: 72.9781 },
  { id: "delhi-connaught", label: "Delhi — Connaught Place", lat: 28.6315, lon: 77.2167 },
  { id: "delhi-rohini", label: "Delhi — Rohini", lat: 28.7495, lon: 77.0627 },
  { id: "gurugram-cyber-city", label: "Gurugram — Cyber City", lat: 28.495, lon: 77.089 },
  { id: "noida-sector-18", label: "Noida — Sector 18", lat: 28.5703, lon: 77.3216 },
  { id: "hyderabad-hitec", label: "Hyderabad — HITEC City", lat: 17.4474, lon: 78.3762 },
  { id: "hyderabad-gachibowli", label: "Hyderabad — Gachibowli", lat: 17.4401, lon: 78.3489 },
  { id: "pune-kothrud", label: "Pune — Kothrud", lat: 18.5074, lon: 73.8077 },
  { id: "pune-viman-nagar", label: "Pune — Viman Nagar", lat: 18.5679, lon: 73.9143 },
  { id: "kolkata-park-street", label: "Kolkata — Park Street area", lat: 22.5511, lon: 88.3527 },
  { id: "ahmedabad-satellite", label: "Ahmedabad — Satellite", lat: 23.0258, lon: 72.5873 },
  { id: "jaipur-vaishali", label: "Jaipur — Vaishali Nagar", lat: 26.9124, lon: 75.7873 },
  { id: "kochi-edappally", label: "Kochi — Edappally", lat: 10.0262, lon: 76.3084 },
  { id: "coimbatore-rs-puram", label: "Coimbatore — RS Puram", lat: 11.0168, lon: 76.9558 },
  { id: "lucknow-gomti", label: "Lucknow — Gomti Nagar", lat: 26.8467, lon: 80.9462 },
  { id: "indore-vijay-nagar", label: "Indore — Vijay Nagar", lat: 22.7533, lon: 75.8937 },
  { id: "chandigarh", label: "Chandigarh — Sector 17", lat: 30.7333, lon: 76.7794 },
  { id: "visakhapatnam-mvp", label: "Visakhapatnam — MVP Colony", lat: 17.7215, lon: 83.318 },
  { id: "bhubaneswar-patia", label: "Bhubaneswar — Patia", lat: 20.356, lon: 85.8246 },
  // Sub-city / neighbourhood (tighter backend fraud radius)
  { id: "chennai-anna-nagar", label: "Chennai — Anna Nagar", lat: 13.0846, lon: 80.2105 },
  { id: "chennai-adyar", label: "Chennai — Adyar", lat: 13.0067, lon: 80.2206 },
  { id: "chennai-porur", label: "Chennai — Porur", lat: 13.0382, lon: 80.1566 },
  { id: "chennai-tambaram", label: "Chennai — Tambaram", lat: 12.9249, lon: 80.1 },
  { id: "bengaluru-hsr-layout", label: "Bengaluru — HSR Layout", lat: 12.9116, lon: 77.6389 },
  { id: "bengaluru-marathahalli", label: "Bengaluru — Marathahalli", lat: 12.9591, lon: 77.6974 },
  { id: "bengaluru-yelahanka", label: "Bengaluru — Yelahanka", lat: 13.1007, lon: 77.5963 },
  { id: "bengaluru-mg-road", label: "Bengaluru — MG Road", lat: 12.9753, lon: 77.6067 },
  { id: "mumbai-bandra", label: "Mumbai — Bandra", lat: 19.0544, lon: 72.8406 },
  { id: "mumbai-powai", label: "Mumbai — Powai", lat: 19.1176, lon: 72.9091 },
  { id: "mumbai-navi-vashi", label: "Mumbai — Navi Mumbai (Vashi)", lat: 19.0807, lon: 73.0103 },
  { id: "delhi-dwarka", label: "Delhi — Dwarka", lat: 28.5921, lon: 77.046 },
  { id: "delhi-saket", label: "Delhi — Saket", lat: 28.5244, lon: 77.2065 },
  { id: "hyderabad-madhapur", label: "Hyderabad — Madhapur", lat: 17.4483, lon: 78.3915 },
  { id: "hyderabad-secunderabad", label: "Hyderabad — Secunderabad", lat: 17.4399, lon: 78.4983 },
  { id: "pune-hinjewadi", label: "Pune — Hinjewadi IT", lat: 18.5912, lon: 73.7389 },
  { id: "kolkata-salt-lake", label: "Kolkata — Salt Lake", lat: 22.5867, lon: 88.4172 },
];

export function zoneById(id: string): WorkZone | undefined {
  return WORK_ZONES.find((z) => z.id === id);
}
