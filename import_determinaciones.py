"""
Script para eliminar todas las determinaciones y cargar las nuevas desde el CSV
"""
import psycopg2
import csv

# Configuración de conexión
DB_CONFIG = {
    'dbname': 'Laboratorio',
    'user': 'postgres',
    'password': 'estufa10',
    'host': 'localhost',
    'port': '5432'
}

CSV_FILE = r"c:\Users\mauro\Downloads\determinaciones - Hoja 1.csv"

def import_determinaciones():
    try:
        # Conectar a la base de datos
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        print("Conectado a la base de datos PostgreSQL")
        
        # Eliminar todas las determinaciones existentes
        cursor.execute("DELETE FROM determinaciones;")
        conn.commit()
        print("✅ Todas las determinaciones anteriores eliminadas")
        
        # Leer CSV e importar datos
        with open(CSV_FILE, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            contador = 0
            duplicados = 0
            
            # Usar un set para detectar duplicados
            determinaciones_insertadas = set()
            
            for row in csv_reader:
                try:
                    # Limpiar espacios en blanco
                    codigo = row['codigo'].strip()
                    nombre = row['nombre'].strip()
                    
                    # Validar que código sea numérico
                    if not codigo.isdigit():
                        print(f"⚠️ Código no numérico ignorado: '{codigo}' - {nombre}")
                        continue
                    
                    codigo_int = int(codigo)
                    
                    # Detectar duplicados (mismo código)
                    if codigo_int in determinaciones_insertadas:
                        duplicados += 1
                        continue
                    
                    # Insertar en la base de datos
                    cursor.execute("""
                        INSERT INTO determinaciones (codigo, nombre)
                        VALUES (%s, %s)
                    """, (codigo_int, nombre))
                    
                    determinaciones_insertadas.add(codigo_int)
                    contador += 1
                    
                except Exception as e:
                    print(f"⚠️ Error procesando fila: {row}")
                    print(f"   Error: {e}")
                    continue
            
            # Confirmar cambios
            conn.commit()
            print(f"\n✅ Importación completada:")
            print(f"   • {contador} determinaciones importadas")
            print(f"   • {duplicados} registros duplicados omitidos")
        
        # Mostrar algunas determinaciones de muestra
        cursor.execute("""
            SELECT codigo, nombre 
            FROM determinaciones 
            ORDER BY codigo 
            LIMIT 10
        """)
        
        print("\n📋 Muestra de determinaciones importadas:")
        for row in cursor.fetchall():
            print(f"   {row[0]}: {row[1]}")
        
        # Mostrar total
        cursor.execute("SELECT COUNT(*) FROM determinaciones")
        total = cursor.fetchone()[0]
        print(f"\n📊 Total de determinaciones en la base de datos: {total}")
        
        # Cerrar conexión
        cursor.close()
        conn.close()
        print("\n✅ Proceso completado exitosamente")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

if __name__ == '__main__':
    import_determinaciones()
