import streamlit as st
from astropy.io import fits
import pandas as pd

st.title("FITS File Viewer")

uploaded_file = st.file_uploader("Upload a FITS file")

if uploaded_file is not None:
    # Convert uploaded file to bytes for caching (UploadedFile objects close after first use)
    file_bytes = uploaded_file.getvalue()
    file_name = uploaded_file.name

    # Cache the FITS file opening to prevent reprocessing on every rerun
    @st.cache_data
    def load_fits_info(file_data):
        """Load FITS file info (HDU summary only, not full data)"""
        from io import BytesIO
        with fits.open(BytesIO(file_data)) as hdul:
            hdu_info = []
            for i, hdu in enumerate(hdul):
                hdu_info.append({
                    'Index': i,
                    'Name': hdu.name,
                    'Type': type(hdu).__name__,
                    'Dimensions': str(hdu.data.shape) if hdu.data is not None else 'No data'
                })
            num_hdus = len(hdul)
        return hdu_info, num_hdus

    @st.cache_data
    def load_hdu_header(file_data, hdu_idx):
        """Load header for specific HDU"""
        from io import BytesIO
        with fits.open(BytesIO(file_data)) as hdul:
            header_data = [[k, str(v), c] for k, v, c in hdul[hdu_idx].header.cards]
        return header_data

    @st.cache_data
    def load_hdu_data(file_data, hdu_idx):
        """Load data for specific HDU"""
        from io import BytesIO
        with fits.open(BytesIO(file_data)) as hdul:
            hdu = hdul[hdu_idx]
            if hdu.data is None:
                return None, None, None, None

            data_shape = hdu.data.shape
            data_dtype = str(hdu.data.dtype)

            # Handle different data types
            if len(hdu.data.shape) == 1 or (len(hdu.data.shape) == 2 and hdu.data.dtype.names):
                # Table data - convert to native byte order
                df = pd.DataFrame(hdu.data).copy()
                for col in df.columns:
                    if df[col].dtype.byteorder not in ('=', '|'):
                        df[col] = df[col].values.astype(df[col].dtype.newbyteorder('='))
                return 'table', df, data_shape, data_dtype
            else:
                # Image data - don't load all into memory
                return 'image', None, data_shape, data_dtype

    # Load basic info
    hdu_info, num_hdus = load_fits_info(file_bytes)

    st.subheader(f"File: {file_name}")
    st.write(f"Number of HDUs: {num_hdus}")

    # Display info about all HDUs
    st.subheader("HDU Summary")
    st.table(pd.DataFrame(hdu_info))

    # Select HDU to view
    hdu_idx = st.selectbox("Select HDU to view", range(num_hdus),
                           format_func=lambda x: f"{x}: {hdu_info[x]['Name']}")

    # Display header
    with st.expander("Header"):
        header_data = load_hdu_header(file_bytes, hdu_idx)
        st.dataframe(pd.DataFrame(header_data, columns=['Keyword', 'Value', 'Comment']),
                     use_container_width=True, height=400)

    # Display data
    data_type, data, data_shape, data_dtype = load_hdu_data(file_bytes, hdu_idx)

    if data_type is None:
        st.info("This HDU contains no data")
    elif data_type == 'table':
        st.subheader("Data")
        st.write(f"Shape: {data_shape} ({data.shape[0]:,} rows)")
        st.dataframe(data, use_container_width=True, height=600)
    elif data_type == 'image':
        st.subheader("Image Data")
        st.write(f"Data shape: {data_shape}")
        st.write(f"Data type: {data_dtype}")
        st.info("Image data detected. Use image processing tools to view the full image.")

        # Option to view sample of flattened data
        if st.checkbox("Show flattened data sample (first 10,000 values)"):
            from io import BytesIO
            with fits.open(BytesIO(file_bytes)) as hdul:
                flat_data = hdul[hdu_idx].data.flatten()[:10000]
                st.dataframe(pd.DataFrame({'Value': flat_data}),
                             use_container_width=True, height=400)
