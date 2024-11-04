import React, { useEffect, useState } from 'react';

const App = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('http://localhost:8080/get_stadium_structure')
      .then(response => {
        if (!response.ok) {
          throw new Error('Error en la solicitud: ' + response.status);
        }
        return response.json();
      })
      .then(data => {
        setData(data);
        setLoading(false);
      })
      .catch(error => {
        setError(error);
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Cargando...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <div>
      <h1>Estructura del Estadio</h1>
      {data ? (
        <div>
          {data.zonas.map((zona, index) => (
            <div key={index}>
              <h2>Zona: {zona.nombre}</h2>
              {Object.entries(zona.categorias).map(([categoria, filas], i) => (
                <div key={i}>
                  <h3>Categoría: {categoria}</h3>
                  {filas.map((fila, filaIndex) => (
                    <div key={filaIndex}>
                      <p>Fila {filaIndex + 1}: {fila.map(asiento => `${asiento.estado}`).join(', ')}</p>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          ))}
        </div>
      ) : (
        <div>No hay datos disponibles</div>
      )}
    </div>
  );
};

export default App;
